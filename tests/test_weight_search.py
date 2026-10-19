"""融合权重网格搜索、数据切分与结果保存测试。"""

import csv
import json

import pytest

from evaluation.weight_search import (
    LabeledScoreCase,
    generate_weight_grid,
    load_labeled_cases,
    run_weight_grid_search,
    save_weight_search_result,
)


def make_cases() -> tuple[LabeledScoreCase, ...]:
    return (
        LabeledScoreCase("v1", "validation", 3, 1.0, 0.4, 0.2, "synthetic_demo"),
        LabeledScoreCase("v2", "validation", 0, 0.0, 0.6, 0.8, "synthetic_demo"),
        LabeledScoreCase("v3", "validation", 2, 0.7, 0.5, 0.4, "synthetic_demo"),
        LabeledScoreCase("t1", "test", 2, 0.8, 0.4, 0.3, "synthetic_demo"),
    )


def test_grid_contains_valid_weights() -> None:
    grid = generate_weight_grid(0.1)
    assert len(grid) == 66
    assert all(weight.semantic + weight.skill + weight.experience == pytest.approx(1) for weight in grid)


def test_grid_search_selects_only_on_validation() -> None:
    cases = make_cases()
    first = run_weight_grid_search(cases, step=0.1)
    changed_test = cases[:-1] + (
        LabeledScoreCase("t1", "test", 0, 0.8, 0.4, 0.3, "synthetic_demo"),
    )
    second = run_weight_grid_search(changed_test, step=0.1)
    assert first.best_validation.weights == second.best_validation.weights
    assert first.test_evaluation.mae != second.test_evaluation.mae


def test_search_requires_separate_test_data() -> None:
    cases = tuple(case for case in make_cases() if case.split == "validation")
    with pytest.raises(ValueError, match="独立测试集"):
        run_weight_grid_search(cases)


def test_load_and_save_experiment_files(tmp_path) -> None:
    input_path = tmp_path / "cases.csv"
    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "case_id",
                "split",
                "relevance_label",
                "semantic_score",
                "skill_score",
                "experience_score",
                "data_status",
            ]
        )
        for case in make_cases():
            writer.writerow(
                [
                    case.case_id,
                    case.split,
                    case.relevance_label,
                    case.semantic_score,
                    case.skill_score,
                    case.experience_score,
                    case.data_status,
                ]
            )
    result = run_weight_grid_search(load_labeled_cases(input_path))
    summary_path, comparison_path = save_weight_search_result(result, tmp_path / "output")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["selection_split"] == "validation"
    assert "synthetic_demo" in summary["data_statuses"]
    assert comparison_path.read_text(encoding="utf-8-sig").startswith("rank,")
