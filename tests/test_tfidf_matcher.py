"""TF-IDF 匹配基线测试。"""

import pytest

from models.tfidf_matcher import calculate_tfidf_similarity


def test_identical_text_has_full_similarity() -> None:
    text = "熟悉 Python 数据分析 SQL"
    assert calculate_tfidf_similarity(text, text) == pytest.approx(1.0)


def test_related_text_scores_higher_than_unrelated_text() -> None:
    resume = "熟悉 Python Flask MySQL 后端开发"
    related_jd = "招聘 Python 后端开发，要求 Flask 和 MySQL"
    unrelated_jd = "招聘视觉设计师，负责品牌插画和海报设计"
    assert calculate_tfidf_similarity(resume, related_jd) > calculate_tfidf_similarity(
        resume, unrelated_jd
    )


def test_disjoint_text_has_zero_similarity() -> None:
    assert calculate_tfidf_similarity("python flask", "海报 插画") == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("resume", "jd", "message"),
    [("", "有效岗位", "简历内容为空"), ("有效简历", "", "岗位 JD 为空")],
)
def test_reject_empty_input(resume: str, jd: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_tfidf_similarity(resume, jd)
