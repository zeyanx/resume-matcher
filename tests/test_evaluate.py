"""阶段 7 完整评估流程测试。"""

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.evaluate import (
    calculate_metrics,
    load_evaluation_cases,
    prediction_functions,
    run_evaluation,
)
from models.fusion_matcher import FusionWeights


DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "evaluation"
    / "synthetic_evaluation_scores.csv"
)


def test_evaluation_data_has_fixed_separate_splits() -> None:
    cases = load_evaluation_cases(DATA_PATH)
    assert len(cases) == 24
    assert sum(case.split == "validation" for case in cases) == 12
    assert sum(case.split == "test" for case in cases) == 12
    assert {case.data_status for case in cases} == {"synthetic_demo"}


def test_metrics_use_only_requested_test_split() -> None:
    cases = load_evaluation_cases(DATA_PATH)
    predictor = prediction_functions(FusionWeights())["BGE"]
    original = calculate_metrics(cases, "BGE", predictor, "test")
    changed = tuple(
        replace(case, semantic_score=1.0 - case.semantic_score)
        if case.split == "validation"
        else case
        for case in cases
    )
    updated = calculate_metrics(changed, "BGE", predictor, "test")
    assert updated == original
    assert original.count == 12
    assert 0 <= original.ndcg_at_5 <= 1
    assert 0 <= original.mrr <= 1


def test_constant_predictions_do_not_invent_correlation() -> None:
    cases = load_evaluation_cases(DATA_PATH)
    metric = calculate_metrics(cases, "常量", lambda case: 0.5, "test")
    assert metric.pearson is None
    assert metric.spearman is None


def test_full_evaluation_saves_required_outputs(tmp_path) -> None:
    cases = load_evaluation_cases(DATA_PATH)
    outputs = run_evaluation(cases, tmp_path, seed=42, weight_step=0.1)
    assert set(outputs) == {
        "metrics",
        "weight_search",
        "ablation",
        "category_metrics",
        "best_config",
        "error_cases",
        "summary",
    }
    assert all(path.exists() for path in outputs.values())
    assert not (tmp_path / "metrics_comparison.png").exists()
    assert outputs["metrics"].read_text(encoding="utf-8-sig").count("\n") == 1

    config = json.loads(outputs["best_config"].read_text(encoding="utf-8"))
    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    assert config["selected_on"] == "validation"
    assert config["random_seed"] == 42
    assert not config["valid_conclusion"]
    assert not config["metrics_generated"]
    assert config["weights"] is None
    assert config["demo_grid_search_weights"] is not None
    assert "尚未形成有效实验结论" in summary["conclusion"]


def test_invalid_evaluation_file_is_rejected(tmp_path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("case_id,query_id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="为空"):
        load_evaluation_cases(path)


def test_partial_annotation_file_can_filter_human_labels(tmp_path) -> None:
    path = tmp_path / "partial.csv"
    fieldnames = [
        "case_id",
        "query_id",
        "split",
        "job_category",
        "relevance_label",
        "label_status",
        "tfidf_score",
        "semantic_score",
        "skill_score",
        "experience_score",
        "data_status",
    ]
    rows = [
        ["v1", "q1", "validation", "前端", 2, "human_labeled", 0.2, 0.7, 0.8, 0.4, "human_labeled"],
        ["t1", "q2", "test", "后端", 1, "human_adjudicated", 0.1, 0.6, 0.5, 0.2, "human_labeled"],
        ["t2", "q3", "test", "后端", "", "pending_human", 0.1, 0.5, 0.4, 0.1, "pending_human"],
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fieldnames)
        writer.writerows(rows)

    cases = load_evaluation_cases(path, human_labeled_only=True)
    assert [case.case_id for case in cases] == ["v1", "t1"]
    with pytest.raises(ValueError, match="尚未完成人工标注"):
        load_evaluation_cases(path)
