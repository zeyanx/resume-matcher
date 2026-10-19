"""技能词典、同义词归一化和差距计算测试。"""

import json

import pytest

from utils.skill_extractor import (
    SkillCatalogError,
    analyze_skill_gap,
    extract_skills,
    load_skill_catalog,
)


def test_catalog_loads_with_unique_canonical_names() -> None:
    catalog = load_skill_catalog()
    names = [item.canonical for item in catalog]
    assert len(catalog) >= 60
    assert len(names) == len(set(names))


def test_synonyms_are_normalized_to_canonical_names() -> None:
    result = extract_skills("熟悉 torch、sklearn 和 k8s，使用 py 开发服务。")
    assert {"PyTorch", "scikit-learn", "Kubernetes", "Python"} <= set(result.skills)
    assert "torch" in result.evidence["PyTorch"]


def test_short_english_aliases_respect_word_boundaries() -> None:
    result = extract_skills("Django developer using JavaScript and Google APIs")
    assert "Django" in result.skills
    assert "JavaScript" in result.skills
    assert "Go" not in result.skills
    assert "Java" not in result.skills


def test_symbol_skills_are_detected() -> None:
    result = extract_skills("使用 C++、C# 与 .NET 进行开发")
    assert {"C++", "C#", ".NET"} <= set(result.skills)


def test_skill_gap_is_explainable() -> None:
    analysis = analyze_skill_gap(
        "Python Flask MySQL Git",
        "要求 Python、Django、MySQL 和 Docker",
    )
    assert analysis.matched_skills == ("MySQL", "Python")
    assert analysis.missing_skills == ("Django", "Docker")
    assert analysis.extra_skills == ("Flask", "Git")
    assert analysis.coverage_rate == pytest.approx(0.5)


def test_no_jd_skills_returns_zero_coverage() -> None:
    analysis = analyze_skill_gap("熟悉 Python", "沟通积极，责任心强")
    assert analysis.jd.skills == ()
    assert analysis.missing_skills == ()
    assert analysis.coverage_rate == 0.0


def test_invalid_catalog_reports_clear_error(tmp_path) -> None:
    catalog_path = tmp_path / "skills.json"
    catalog_path.write_text(json.dumps({"skills": []}), encoding="utf-8")
    with pytest.raises(SkillCatalogError, match="非空"):
        load_skill_catalog(catalog_path)
