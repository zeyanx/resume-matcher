"""严格使用验证集选权重、隔离测试集评估的网格搜索。"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean

from scipy.stats import spearmanr

from models.fusion_matcher import FusionWeights, calculate_fusion_score


ALLOWED_SPLITS = {"validation", "test"}


@dataclass(frozen=True, slots=True)
class LabeledScoreCase:
    """一条带 0–3 人工相关性标签的预计算子分数记录。"""

    case_id: str
    split: str
    relevance_label: float
    semantic_score: float
    skill_score: float
    experience_score: float
    data_status: str = "unknown"

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id 不能为空。")
        if self.split not in ALLOWED_SPLITS:
            raise ValueError("split 必须是 validation 或 test。")
        if not math.isfinite(self.relevance_label) or not 0 <= self.relevance_label <= 3:
            raise ValueError("relevance_label 必须是 0 到 3 之间的数值。")
        for name, value in (
            ("semantic_score", self.semantic_score),
            ("skill_score", self.skill_score),
            ("experience_score", self.experience_score),
        ):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} 必须是 0 到 1 之间的数值。")

    @property
    def normalized_label(self) -> float:
        """将 0–3 标签映射到与模型分数一致的 0–1。"""
        return self.relevance_label / 3.0


@dataclass(frozen=True, slots=True)
class WeightEvaluation:
    """一组权重在固定数据切分上的误差。"""

    weights: FusionWeights
    split: str
    count: int
    spearman: float | None
    mae: float
    rmse: float


@dataclass(frozen=True, slots=True)
class WeightSearchResult:
    """验证集搜索结果与隔离测试集的一次性评估。"""

    best_validation: WeightEvaluation
    test_evaluation: WeightEvaluation
    comparisons: tuple[WeightEvaluation, ...]
    step: float
    data_statuses: tuple[str, ...]


def load_labeled_cases(path: str | Path) -> tuple[LabeledScoreCase, ...]:
    """从 CSV 读取预计算子分数与人工标签。"""
    input_path = Path(path)
    try:
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise ValueError(f"无法读取权重实验数据：{input_path}") from exc
    if not rows:
        raise ValueError("权重实验数据为空。")

    cases: list[LabeledScoreCase] = []
    for line_number, row in enumerate(rows, start=2):
        if not str(row.get("relevance_label", "")).strip():
            raise ValueError(f"权重实验数据第 {line_number} 行尚未完成人工标注。")
        label_status = str(row.get("label_status", "")).strip()
        if label_status and label_status not in {"human_labeled", "human_adjudicated"}:
            raise ValueError(
                f"权重实验数据第 {line_number} 行 label_status={label_status}，"
                "只有真人标注可用于调参。"
            )
        try:
            cases.append(
                LabeledScoreCase(
                    case_id=row["case_id"].strip(),
                    split=row["split"].strip().lower(),
                    relevance_label=float(row["relevance_label"]),
                    semantic_score=float(row["semantic_score"]),
                    skill_score=float(row["skill_score"]),
                    experience_score=float(row["experience_score"]),
                    data_status=row.get("data_status", "unknown").strip() or "unknown",
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"权重实验数据第 {line_number} 行格式错误：{exc}") from exc
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("权重实验数据的 case_id 必须唯一。")
    return tuple(cases)


def generate_weight_grid(step: float = 0.1) -> tuple[FusionWeights, ...]:
    """生成非负且和为 1 的三维权重网格。"""
    if not math.isfinite(step) or step <= 0 or step > 1:
        raise ValueError("网格步长必须在 0 到 1 之间。")
    units_float = 1.0 / step
    units = round(units_float)
    if not math.isclose(units_float, units, abs_tol=1e-9):
        raise ValueError("网格步长必须能整除 1，例如 0.1、0.2 或 0.25。")

    weights: list[FusionWeights] = []
    for semantic_units in range(units + 1):
        for skill_units in range(units - semantic_units + 1):
            experience_units = units - semantic_units - skill_units
            weights.append(
                FusionWeights(
                    semantic=semantic_units / units,
                    skill=skill_units / units,
                    experience=experience_units / units,
                )
            )
    return tuple(weights)


def evaluate_weights(
    cases: tuple[LabeledScoreCase, ...],
    weights: FusionWeights,
    split: str,
) -> WeightEvaluation:
    """只评估指定切分，防止选权重时混入测试集。"""
    selected = tuple(case for case in cases if case.split == split)
    if not selected:
        raise ValueError(f"没有可用的 {split} 数据。")
    errors: list[float] = []
    squared_errors: list[float] = []
    labels: list[float] = []
    predictions: list[float] = []
    for case in selected:
        prediction = calculate_fusion_score(
            case.semantic_score,
            case.skill_score,
            case.experience_score,
            weights,
        ).score
        error = prediction - case.normalized_label
        errors.append(abs(error))
        squared_errors.append(error * error)
        labels.append(case.normalized_label)
        predictions.append(prediction)
    correlation = None
    if len(set(labels)) > 1 and len(set(predictions)) > 1:
        statistic = float(spearmanr(labels, predictions).statistic)
        if math.isfinite(statistic):
            correlation = statistic
    return WeightEvaluation(
        weights=weights,
        split=split,
        count=len(selected),
        spearman=correlation,
        mae=fmean(errors),
        rmse=math.sqrt(fmean(squared_errors)),
    )


def run_weight_grid_search(
    cases: tuple[LabeledScoreCase, ...],
    step: float = 0.1,
) -> WeightSearchResult:
    """仅按验证集 Spearman 选择权重，再在测试集上评估一次。"""
    validation_count = sum(case.split == "validation" for case in cases)
    test_count = sum(case.split == "test" for case in cases)
    if validation_count < 2 or test_count < 1:
        raise ValueError("至少需要 2 条验证集记录和 1 条独立测试集记录。")

    comparisons = tuple(
        evaluate_weights(cases, weights, "validation") for weights in generate_weight_grid(step)
    )
    default = FusionWeights()
    best = min(
        comparisons,
        key=lambda item: (
            -(item.spearman if item.spearman is not None else -1.0),
            item.mae,
            item.rmse,
            abs(item.weights.semantic - default.semantic)
            + abs(item.weights.skill - default.skill)
            + abs(item.weights.experience - default.experience),
            -item.weights.semantic,
            -item.weights.skill,
        ),
    )
    test_evaluation = evaluate_weights(cases, best.weights, "test")
    return WeightSearchResult(
        best_validation=best,
        test_evaluation=test_evaluation,
        comparisons=tuple(
            sorted(
                comparisons,
                key=lambda item: (
                    -(item.spearman if item.spearman is not None else -1.0),
                    item.mae,
                    item.rmse,
                ),
            )
        ),
        step=step,
        data_statuses=tuple(sorted({case.data_status for case in cases})),
    )


def save_weight_search_result(
    result: WeightSearchResult,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """保存最佳权重和完整验证集对比表。"""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_path = destination / "best_fusion_weights.json"
    comparison_path = destination / "weight_comparison.csv"

    summary = {
        "weights": asdict(result.best_validation.weights),
        "selection_split": "validation",
        "selection_metric": "Spearman（并列时依次比较 MAE、RMSE）",
        "validation": {
            "count": result.best_validation.count,
            "spearman": result.best_validation.spearman,
            "mae": result.best_validation.mae,
            "rmse": result.best_validation.rmse,
        },
        "test": {
            "count": result.test_evaluation.count,
            "spearman": result.test_evaluation.spearman,
            "mae": result.test_evaluation.mae,
            "rmse": result.test_evaluation.rmse,
        },
        "grid_step": result.step,
        "data_statuses": list(result.data_statuses),
        "warning": (
            "synthetic_demo 只验证流程；FairCV 人工标注结果也只代表合成简历与固定 JD 样本，"
            "不代表真实招聘准确率或生产最优权重。"
        ),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with comparison_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rank",
                "semantic_weight",
                "skill_weight",
                "experience_weight",
                "validation_count",
                "validation_spearman",
                "validation_mae",
                "validation_rmse",
            ],
        )
        writer.writeheader()
        for rank, evaluation in enumerate(result.comparisons, start=1):
            writer.writerow(
                {
                    "rank": rank,
                    "semantic_weight": evaluation.weights.semantic,
                    "skill_weight": evaluation.weights.skill,
                    "experience_weight": evaluation.weights.experience,
                    "validation_count": evaluation.count,
                    "validation_spearman": evaluation.spearman,
                    "validation_mae": evaluation.mae,
                    "validation_rmse": evaluation.rmse,
                }
            )
    return summary_path, comparison_path
