"""经历关键词覆盖分析测试。"""

import json

import pytest

from models.experience_matcher import (
    ExperienceCatalogError,
    calculate_experience_match,
    extract_experience_keywords,
    load_experience_catalog,
)


def test_experience_catalog_loads() -> None:
    catalog = load_experience_catalog()
    assert len(catalog) >= 20
    assert len({item.canonical for item in catalog}) == len(catalog)


def test_experience_aliases_are_normalized() -> None:
    result = extract_experience_keywords(
        "负责 architecture design、testing、deployment，并参与团队协作。"
    )
    assert {"系统设计", "测试", "部署", "团队协作"} <= set(result.keywords)


def test_experience_keyword_coverage() -> None:
    result = calculate_experience_match(
        "参与软件开发、测试和技术文档编写。",
        "负责软件开发、测试、部署和技术文档。",
    )
    assert result.is_available
    assert result.matched_keywords == ("文档", "测试", "软件开发")
    assert result.missing_keywords == ("部署",)
    assert result.score == pytest.approx(0.75)
    assert "不推断工作年限" in result.years_status


def test_no_jd_keyword_is_explicitly_unavailable() -> None:
    result = calculate_experience_match("负责软件开发", "认真负责，积极主动")
    assert not result.is_available
    assert result.score == 0.0


def test_invalid_experience_catalog(tmp_path) -> None:
    path = tmp_path / "experience.json"
    path.write_text(json.dumps({"keywords": []}), encoding="utf-8")
    with pytest.raises(ExperienceCatalogError, match="非空"):
        load_experience_catalog(path)
