"""可复现的算法对比、消融、分类别和错误案例评估。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.stats import pearsonr, spearmanr  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    f1_score,
    ndcg_score,
    precision_score,
    recall_score,
)

from evaluation.weight_search import (  # noqa: E402
    LabeledScoreCase,
    run_weight_grid_search,
)
from models.fusion_matcher import FusionWeights, calculate_fusion_score  # noqa: E402


ALGORITHMS = ("TF-IDF", "BGE", "融合评分", "去除技能的融合")


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """带岗位分组、固定切分和预计算算法子分数的案例。"""

    case_id: str
    query_id: str
    split: str
    job_category: str
    relevance_label: float
    tfidf_score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    data_status: str

    def __post_init__(self) -> None:
        if not self.case_id or not self.query_id or not self.job_category:
            raise ValueError("case_id、query_id 和 job_category 不能为空。")
        if self.split not in {"validation", "test"}:
            raise ValueError("split 必须是 validation 或 test。")
        if not 0 <= self.relevance_label <= 3:
            raise ValueError("relevance_label 必须在 0 到 3 之间。")
        for value in (
            self.tfidf_score,
            self.semantic_score,
            self.skill_score,
            self.experience_score,
        ):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("所有算法子分数必须是 0 到 1 之间的有限数值。")

    @property
    def normalized_label(self) -> float:
        return self.relevance_label / 3.0


@dataclass(frozen=True, slots=True)
class MetricResult:
    """一项算法在一个固定数据子集上的指标。"""

    algorithm: str
    split: str
    category: str
    count: int
    pearson: float | None
    spearman: float | None
    ndcg_at_5: float
    mrr: float
    accuracy: float
    precision: float
    recall: float
    f1: float
    mae: float
    rmse: float


def load_evaluation_cases(path: str | Path) -> tuple[EvaluationCase, ...]:
    """读取完整评估 CSV；不自动或随机重划分数据。"""
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise ValueError(f"无法读取评估数据：{source}") from exc
    if not rows:
        raise ValueError("评估数据为空。")

    cases: list[EvaluationCase] = []
    for line_number, row in enumerate(rows, start=2):
        if not str(row.get("relevance_label", "")).strip():
            raise ValueError(f"评估数据第 {line_number} 行尚未完成人工标注。")
        label_status = str(row.get("label_status", "")).strip()
        if label_status and label_status not in {"human_labeled", "human_adjudicated"}:
            raise ValueError(
                f"评估数据第 {line_number} 行 label_status={label_status}，"
                "只有真人标注可用于正式评估。"
            )
        try:
            cases.append(
                EvaluationCase(
                    case_id=row["case_id"].strip(),
                    query_id=row["query_id"].strip(),
                    split=row["split"].strip().lower(),
                    job_category=row["job_category"].strip(),
                    relevance_label=float(row["relevance_label"]),
                    tfidf_score=float(row["tfidf_score"]),
                    semantic_score=float(row["semantic_score"]),
                    skill_score=float(row["skill_score"]),
                    experience_score=float(row["experience_score"]),
                    data_status=row.get("data_status", "unknown").strip() or "unknown",
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"评估数据第 {line_number} 行格式错误：{exc}") from exc
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("评估数据的 case_id 必须唯一。")
    if not any(case.split == "validation" for case in cases):
        raise ValueError("评估数据缺少 validation 切分。")
    if not any(case.split == "test" for case in cases):
        raise ValueError("评估数据缺少 test 切分。")
    return tuple(cases)


def prediction_functions(weights: FusionWeights) -> dict[str, Callable[[EvaluationCase], float]]:
    """构建四种待比较算法，消融模型会重新归一化剩余权重。"""
    remaining = weights.semantic + weights.experience
    if remaining <= 0:
        raise ValueError("去除技能特征后，语义和经历权重之和必须大于 0。")
    no_skill_weights = FusionWeights(
        semantic=weights.semantic / remaining,
        skill=0.0,
        experience=weights.experience / remaining,
    )
    return {
        "TF-IDF": lambda case: case.tfidf_score,
        "BGE": lambda case: case.semantic_score,
        "融合评分": lambda case: calculate_fusion_score(
            case.semantic_score,
            case.skill_score,
            case.experience_score,
            weights,
        ).score,
        "去除技能的融合": lambda case: calculate_fusion_score(
            case.semantic_score,
            case.skill_score,
            case.experience_score,
            no_skill_weights,
        ).score,
    }


def _safe_correlation(
    function: Callable[[np.ndarray, np.ndarray], object],
    labels: np.ndarray,
    predictions: np.ndarray,
) -> float | None:
    """常量数组不伪造相关系数，返回空值。"""
    if len(labels) < 2 or np.ptp(labels) == 0 or np.ptp(predictions) == 0:
        return None
    result = function(labels, predictions)
    value = float(getattr(result, "statistic", result[0]))
    return value if math.isfinite(value) else None


def _ranking_metrics(
    cases: tuple[EvaluationCase, ...],
    predictions: np.ndarray,
    relevant_label: float = 2.0,
) -> tuple[float, float]:
    """按 query_id 计算平均 NDCG@5 和 MRR。"""
    grouped_indices: dict[str, list[int]] = {}
    for index, case in enumerate(cases):
        grouped_indices.setdefault(case.query_id, []).append(index)

    ndcg_values: list[float] = []
    reciprocal_ranks: list[float] = []
    for indices in grouped_indices.values():
        labels = np.array([cases[index].relevance_label for index in indices], dtype=float)
        scores = predictions[indices]
        ndcg_values.append(float(ndcg_score([labels], [scores], k=min(5, len(indices)))))
        ranked = sorted(indices, key=lambda index: (-predictions[index], cases[index].case_id))
        reciprocal_rank = 0.0
        for rank, index in enumerate(ranked, start=1):
            if cases[index].relevance_label >= relevant_label:
                reciprocal_rank = 1.0 / rank
                break
        reciprocal_ranks.append(reciprocal_rank)
    return float(np.mean(ndcg_values)), float(np.mean(reciprocal_ranks))


def calculate_metrics(
    cases: tuple[EvaluationCase, ...],
    algorithm: str,
    predictor: Callable[[EvaluationCase], float],
    split: str,
    category: str = "全部",
    classification_threshold: float = 0.5,
) -> MetricResult:
    """对固定切分和类别计算相关性、排序、分类及误差指标。"""
    selected = tuple(
        case
        for case in cases
        if case.split == split and (category == "全部" or case.job_category == category)
    )
    if not selected:
        raise ValueError(f"没有 {split}/{category} 的评估数据。")
    labels = np.array([case.normalized_label for case in selected], dtype=float)
    predictions = np.array([predictor(case) for case in selected], dtype=float)
    pearson = _safe_correlation(pearsonr, labels, predictions)
    spearman = _safe_correlation(spearmanr, labels, predictions)
    ndcg, mrr = _ranking_metrics(selected, predictions)
    true_binary = np.array([case.relevance_label >= 2 for case in selected], dtype=int)
    predicted_binary = (predictions >= classification_threshold).astype(int)
    errors = predictions - labels
    return MetricResult(
        algorithm=algorithm,
        split=split,
        category=category,
        count=len(selected),
        pearson=pearson,
        spearman=spearman,
        ndcg_at_5=ndcg,
        mrr=mrr,
        accuracy=float(accuracy_score(true_binary, predicted_binary)),
        precision=float(precision_score(true_binary, predicted_binary, zero_division=0)),
        recall=float(recall_score(true_binary, predicted_binary, zero_division=0)),
        f1=float(f1_score(true_binary, predicted_binary, zero_division=0)),
        mae=float(np.mean(np.abs(errors))),
        rmse=float(np.sqrt(np.mean(errors**2))),
    )


def _write_metrics(path: Path, metrics: tuple[MetricResult, ...]) -> None:
    """保存指标表，None 相关系数写为空单元格。"""
    fieldnames = list(asdict(metrics[0]).keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for metric in metrics:
            writer.writerow(asdict(metric))


def _write_empty_metrics(path: Path) -> None:
    """为未具备真实标注的数据写出待填充表头，不保存演示指标。"""
    fieldnames = list(MetricResult.__dataclass_fields__)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()


def _save_weight_search(path: Path, comparisons: tuple[object, ...]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "semantic_weight",
                "skill_weight",
                "experience_weight",
                "validation_count",
                "validation_spearman",
                "validation_mae",
                "validation_rmse",
            ]
        )
        for rank, item in enumerate(comparisons, start=1):
            writer.writerow(
                [
                    rank,
                    item.weights.semantic,
                    item.weights.skill,
                    item.weights.experience,
                    item.count,
                    item.spearman,
                    item.mae,
                    item.rmse,
                ]
            )


def _save_error_cases(
    path: Path,
    cases: tuple[EvaluationCase, ...],
    predictors: dict[str, Callable[[EvaluationCase], float]],
) -> None:
    rows: list[dict[str, object]] = []
    test_cases = tuple(case for case in cases if case.split == "test")
    for algorithm, predictor in predictors.items():
        for case in test_cases:
            prediction = predictor(case)
            rows.append(
                {
                    "algorithm": algorithm,
                    "case_id": case.case_id,
                    "query_id": case.query_id,
                    "job_category": case.job_category,
                    "relevance_label": case.relevance_label,
                    "prediction": prediction,
                    "absolute_error": abs(prediction - case.normalized_label),
                    "data_status": case.data_status,
                }
            )
    rows.sort(key=lambda row: (-float(row["absolute_error"]), str(row["case_id"])))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows[:20])


def _save_charts(
    output_dir: Path,
    metrics: tuple[MetricResult, ...],
    category_metrics: tuple[MetricResult, ...],
) -> None:
    """保存三张无需图形界面的 PNG 图表。"""
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    names = [metric.algorithm for metric in metrics]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    width = 0.25
    ax.bar(x - width, [metric.pearson or 0 for metric in metrics], width, label="Pearson")
    ax.bar(x, [metric.spearman or 0 for metric in metrics], width, label="Spearman")
    ax.bar(x + width, [metric.ndcg_at_5 for metric in metrics], width, label="NDCG@5")
    ax.set_xticks(x, names, rotation=12)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("指标值")
    ax.set_title("测试集算法指标对比")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "metrics_comparison.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(names, [metric.mae for metric in metrics], color="#4C78A8")
    ax.set_ylabel("MAE（越低越好）")
    ax.set_title("测试集消融与算法误差")
    ax.tick_params(axis="x", rotation=12)
    fig.tight_layout()
    fig.savefig(output_dir / "ablation_mae.png", dpi=160)
    plt.close(fig)

    fusion_by_category = [
        metric for metric in category_metrics if metric.algorithm == "融合评分"
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(
        [metric.category for metric in fusion_by_category],
        [metric.mae for metric in fusion_by_category],
        color="#59A14F",
    )
    ax.set_ylabel("MAE（越低越好）")
    ax.set_title("融合评分分岗位类别误差")
    fig.tight_layout()
    fig.savefig(output_dir / "category_fusion_mae.png", dpi=160)
    plt.close(fig)


def run_evaluation(
    cases: tuple[EvaluationCase, ...],
    output_dir: str | Path,
    seed: int = 42,
    weight_step: float = 0.1,
    classification_threshold: float = 0.5,
) -> dict[str, Path]:
    """运行完整评估并将所有结果保存到 reports 目录。"""
    np.random.seed(seed)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    score_cases = tuple(
        LabeledScoreCase(
            case_id=case.case_id,
            split=case.split,
            relevance_label=case.relevance_label,
            semantic_score=case.semantic_score,
            skill_score=case.skill_score,
            experience_score=case.experience_score,
            data_status=case.data_status,
        )
        for case in cases
    )
    search = run_weight_grid_search(score_cases, step=weight_step)
    weights = search.best_validation.weights
    predictors = prediction_functions(weights)

    metrics_path = destination / "metrics.csv"
    ablation_path = destination / "ablation_results.csv"
    category_path = destination / "category_metrics.csv"
    weights_path = destination / "weight_search.csv"
    config_path = destination / "best_config.json"
    errors_path = destination / "error_cases.csv"
    summary_path = destination / "run_summary.json"

    _save_weight_search(weights_path, search.comparisons)

    data_statuses = sorted({case.data_status for case in cases})
    has_synthetic_data = "synthetic_demo" in data_statuses
    metrics_generated = not has_synthetic_data
    if metrics_generated:
        metrics = tuple(
            calculate_metrics(
                cases,
                algorithm,
                predictor,
                split="test",
                classification_threshold=classification_threshold,
            )
            for algorithm, predictor in predictors.items()
        )
        categories = tuple(sorted({case.job_category for case in cases if case.split == "test"}))
        category_metrics = tuple(
            calculate_metrics(
                cases,
                algorithm,
                predictor,
                split="test",
                category=category,
                classification_threshold=classification_threshold,
            )
            for category in categories
            for algorithm, predictor in predictors.items()
        )
        _write_metrics(metrics_path, metrics)
        _write_metrics(
            ablation_path,
            tuple(metric for metric in metrics if "融合" in metric.algorithm),
        )
        _write_metrics(category_path, category_metrics)
        _save_error_cases(errors_path, cases, predictors)
        _save_charts(destination, metrics, category_metrics)
    else:
        _write_empty_metrics(metrics_path)
        _write_empty_metrics(ablation_path)
        _write_empty_metrics(category_path)
        with errors_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "algorithm",
                    "case_id",
                    "query_id",
                    "job_category",
                    "relevance_label",
                    "prediction",
                    "absolute_error",
                    "data_status",
                ]
            )

    config = {
        "weights": asdict(weights) if metrics_generated else None,
        "demo_grid_search_weights": asdict(weights) if has_synthetic_data else None,
        "selected_on": "validation",
        "selection_metric": "Spearman（并列时依次比较 MAE、RMSE）",
        "weight_step": weight_step,
        "classification_threshold": classification_threshold,
        "random_seed": seed,
        "split_strategy": "使用输入文件中预先固定的 validation/test，不进行随机重划分",
        "data_statuses": data_statuses,
        "valid_conclusion": metrics_generated,
        "metrics_generated": metrics_generated,
        "evidence_note": (
            "合成数据仅用于流程检查；best_config 中不保存可用于结论的正式权重。"
            if has_synthetic_data
            else "指标来自提供的固定人工标注测试集。"
        ),
    }
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    output_names = [
        metrics_path.name,
        weights_path.name,
        ablation_path.name,
        category_path.name,
        config_path.name,
        errors_path.name,
    ]
    if metrics_generated:
        output_names.extend(
            ["metrics_comparison.png", "ablation_mae.png", "category_fusion_mae.png"]
        )
    summary = {
        "validation_count": sum(case.split == "validation" for case in cases),
        "test_count": sum(case.split == "test" for case in cases),
        "query_count": len({case.query_id for case in cases}),
        "job_categories": sorted({case.job_category for case in cases}),
        "algorithms": list(predictors),
        "outputs": output_names,
        "data_statuses": data_statuses,
        "metrics_generated": metrics_generated,
        "conclusion": (
            "尚未形成有效实验结论：当前只有合成演示数据，指标表仅保留表头。"
            if has_synthetic_data
            else "指标来自提供的固定测试集；解释时仍需结合数据卡和标注质量。"
        ),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "metrics": metrics_path,
        "weight_search": weights_path,
        "ablation": ablation_path,
        "category_metrics": category_path,
        "best_config": config_path,
        "error_cases": errors_path,
        "summary": summary_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行 ResumeMatcher 完整评估。")
    parser.add_argument("--input", type=Path, required=True, help="预计算分数与标签 CSV。")
    parser.add_argument("--output-dir", type=Path, required=True, help="结果保存目录。")
    parser.add_argument("--seed", type=int, default=42, help="随机种子记录，默认 42。")
    parser.add_argument("--weight-step", type=float, default=0.1, help="权重网格步长。")
    parser.add_argument("--classification-threshold", type=float, default=0.5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_evaluation_cases(args.input)
    outputs = run_evaluation(
        cases,
        args.output_dir,
        seed=args.seed,
        weight_step=args.weight_step,
        classification_threshold=args.classification_threshold,
    )
    statuses = sorted({case.data_status for case in cases})
    print(f"数据状态：{', '.join(statuses)}")
    if "synthetic_demo" in statuses:
        print("尚未形成有效实验结论：当前只有合成演示数据，指标表仅保留表头。")
    for name, path in outputs.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
