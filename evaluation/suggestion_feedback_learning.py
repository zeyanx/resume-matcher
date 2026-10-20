"""用人工审核后的“有用建议”选择训练透明的建议排序模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score


PRIORITY_SCORE = {"高": 1.0, "中": 0.5, "低": 0.0}


@dataclass(frozen=True, slots=True)
class SuggestionLearningResult:
    submission_count: int
    training_item_count: int
    test_item_count: int
    test_accuracy: float
    test_roc_auc: float | None
    kind_weights: dict[str, float]
    kind_probabilities: dict[str, float]


def _decoded_list(row: Mapping[str, object], key: str) -> list[str]:
    value = row.get(key, "[]")
    decoded = json.loads(str(value)) if not isinstance(value, (list, tuple)) else value
    return [str(item) for item in decoded]


def train_suggestion_policy(
    rows: Iterable[Mapping[str, object]], minimum_records: int = 30
) -> SuggestionLearningResult:
    """按提交记录切分训练/测试，避免同一次反馈泄漏到两侧。"""
    records = list(rows)
    if len(records) < minimum_records:
        raise ValueError(f"已审核建议反馈只有 {len(records)} 条；至少需要 {minimum_records} 条。")
    kinds = sorted({kind for row in records for kind in _decoded_list(row, "suggestion_kinds_json")})
    if not kinds:
        raise ValueError("建议反馈中没有可学习的建议类别。")
    kind_index = {kind: index for index, kind in enumerate(kinds)}

    features: list[list[float]] = []
    labels: list[int] = []
    weights: list[float] = []
    splits: list[str] = []
    for row in records:
        row_kinds = _decoded_list(row, "suggestion_kinds_json")
        priorities = _decoded_list(row, "suggestion_priorities_json")
        helpful = set(_decoded_list(row, "helpful_kinds_json"))
        rating = int(row.get("satisfaction_rating", 3))
        sample_weight = 1.0 + abs(rating - 3) * 0.5
        context = [
            float(row.get("skill_coverage") or 0.0),
            float(row.get("experience_score") or 0.0),
            min(float(row.get("missing_skill_count") or 0.0), 20.0) / 20.0,
            min(float(row.get("missing_experience_count") or 0.0), 20.0) / 20.0,
            min(float(row.get("resume_length") or 0.0), 50_000.0) / 50_000.0,
            min(float(row.get("jd_length") or 0.0), 50_000.0) / 50_000.0,
        ]
        for position, kind in enumerate(row_kinds):
            one_hot = [0.0] * len(kinds)
            one_hot[kind_index[kind]] = 1.0
            priority = priorities[position] if position < len(priorities) else "中"
            features.append(one_hot + [PRIORITY_SCORE.get(priority, 0.5)] + context)
            labels.append(int(kind in helpful))
            weights.append(sample_weight)
            splits.append(str(row.get("split", "validation")))

    matrix = np.asarray(features, dtype=float)
    targets = np.asarray(labels, dtype=int)
    sample_weights = np.asarray(weights, dtype=float)
    train_mask = np.asarray([split != "test" for split in splits], dtype=bool)
    test_mask = ~train_mask
    if not train_mask.any() or not test_mask.any():
        raise ValueError("已审核反馈必须同时包含 validation 和 test 切分。")
    if len(np.unique(targets[train_mask])) < 2:
        raise ValueError("训练切分必须同时包含“有用”和“未选中”建议。")

    model = LogisticRegression(C=1.0, max_iter=2_000, random_state=42)
    model.fit(matrix[train_mask], targets[train_mask], sample_weight=sample_weights[train_mask])
    test_probabilities = model.predict_proba(matrix[test_mask])[:, 1]
    test_predictions = (test_probabilities >= 0.5).astype(int)
    accuracy = float(accuracy_score(targets[test_mask], test_predictions))
    auc = (
        float(roc_auc_score(targets[test_mask], test_probabilities))
        if len(np.unique(targets[test_mask])) == 2
        else None
    )

    context_columns = matrix[:, len(kinds) + 1 :]
    median_context = np.median(context_columns, axis=0).tolist()
    kind_probabilities: dict[str, float] = {}
    for kind in kinds:
        one_hot = [0.0] * len(kinds)
        one_hot[kind_index[kind]] = 1.0
        neutral_row = np.asarray([one_hot + [0.5] + median_context], dtype=float)
        kind_probabilities[kind] = float(model.predict_proba(neutral_row)[0, 1])
    mean_probability = max(float(np.mean(list(kind_probabilities.values()))), 1e-6)
    kind_weights = {
        kind: round(float(np.clip(probability / mean_probability, 0.75, 1.25)), 4)
        for kind, probability in kind_probabilities.items()
    }
    return SuggestionLearningResult(
        submission_count=len(records),
        training_item_count=int(train_mask.sum()),
        test_item_count=int(test_mask.sum()),
        test_accuracy=accuracy,
        test_roc_auc=auc,
        kind_weights=kind_weights,
        kind_probabilities=kind_probabilities,
    )


def save_candidate_policy(
    result: SuggestionLearningResult, output_dir: Path, minimum_records: int
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = output_dir / "candidate_suggestion_policy.json"
    metrics_path = output_dir / "suggestion_learning_metrics.json"
    timestamp = datetime.now(timezone.utc).isoformat()
    candidate = {
        "version": f"candidate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "status": "candidate_not_applied",
        "source": "人工审核通过的建议满意度反馈；LogisticRegression 有用建议预测",
        "learned_from": result.submission_count,
        "minimum_approved_records": minimum_records,
        "kind_weights": result.kind_weights,
        "created_at": timestamp,
    }
    metrics = {
        "created_at": timestamp,
        "submission_count": result.submission_count,
        "training_item_count": result.training_item_count,
        "test_item_count": result.test_item_count,
        "test_accuracy": result.test_accuracy,
        "test_roc_auc": result.test_roc_auc,
        "kind_probabilities": result.kind_probabilities,
        "notes": "测试指标仅反映已审核反馈；候选策略不会自动上线。",
    }
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return candidate_path, metrics_path
