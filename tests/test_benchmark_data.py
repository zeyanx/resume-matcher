"""FairCV + 公开 JD 基准的数据结构和安全边界测试。"""

import csv
import json
from pathlib import Path

import pytest

from evaluation.evaluate import load_evaluation_cases
from utils.benchmark_data import parse_job_markup


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_CASES = PROJECT_ROOT / "data" / "test_cases.csv"


def test_job_markup_parser_keeps_title_description_and_education() -> None:
    title, description, education = parse_job_markup(
        "<岗位名称>机器学习工程师</岗位名称>"
        "<岗位描述>负责模型训练与部署。</岗位描述>"
        "<学历描述>本科及以上</学历描述>"
    )
    assert title == "机器学习工程师"
    assert description == "负责模型训练与部署。"
    assert education == "本科及以上"


def test_pending_benchmark_has_expected_fixed_structure() -> None:
    with TEST_CASES.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 300
    assert len({row["resume_id"] for row in rows}) == 60
    assert len({row["jd_id"] for row in rows}) == 300
    assert sum(row["split"] == "validation" for row in rows) == 60
    assert sum(row["split"] == "test" for row in rows) == 240
    assert {row["label_status"] for row in rows} == {"pending_human"}
    assert {row["relevance_label"] for row in rows} == {""}
    assert all(row["jd_text"].startswith("岗位名称：") for row in rows)
    for field in ("tfidf_score", "semantic_score", "skill_score", "experience_score"):
        assert all(0 <= float(row[field]) <= 1 for row in rows)


def test_pending_benchmark_cannot_be_reported_as_formal_evaluation() -> None:
    with pytest.raises(ValueError, match="尚未完成人工标注"):
        load_evaluation_cases(TEST_CASES)


def test_five_faircv_examples_are_source_references_not_raw_resumes() -> None:
    path = PROJECT_ROOT / "data" / "sample_resumes" / "faircv_examples.json"
    examples = json.loads(path.read_text(encoding="utf-8"))
    assert len(examples) == 5
    assert len({item["position"] for item in examples}) == 5
    assert all(isinstance(item["source_row_index"], int) for item in examples)
    assert all("text" not in item for item in examples)
