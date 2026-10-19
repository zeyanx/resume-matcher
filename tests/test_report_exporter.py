"""Markdown/TXT 报告导出测试。"""

from datetime import datetime, timezone

import pytest

from models.suggestion import ResumeSuggestion
from utils.report_exporter import (
    AnalysisReportData,
    build_text_signature,
    make_report_filename,
    render_markdown_report,
    render_text_report,
)


def make_report_data() -> AnalysisReportData:
    return AnalysisReportData(
        generated_at=datetime(2026, 10, 19, 12, 30, tzinfo=timezone.utc),
        scores={
            "tfidf": 0.42,
            "semantic": 0.83,
            "skill": 0.75,
            "experience": 0.5,
            "fusion": 0.72,
        },
        matched_skills=("Python", "MySQL"),
        missing_skills=("Docker",),
        matched_experience=("测试",),
        missing_experience=("部署",),
        suggestions=(
            ResumeSuggestion("核对技能", "若确实掌握再补充证据。", "缺失 Docker", "高"),
        ),
        weights=(0.5, 0.3, 0.2),
        weight_source="未经真实标注验证",
    )


def test_markdown_report_contains_required_sections() -> None:
    report = render_markdown_report(make_report_data())
    assert "生成时间" in report
    assert "BGE 语义匹配度：83.00%" in report
    assert "缺失技能：Docker" in report
    assert "优化建议" in report
    assert "算法说明" in report
    assert "不附带完整简历或 JD 正文" in report


def test_text_report_removes_markdown_headings() -> None:
    report = render_text_report(make_report_data())
    assert "# " not in report
    assert "智能简历岗位匹配分析报告" in report
    assert "• 融合评分：72.00%" in report


def test_signature_changes_with_either_text() -> None:
    first = build_text_signature("resume", "jd")
    assert first == build_text_signature("resume", "jd")
    assert first != build_text_signature("resume changed", "jd")
    assert first != build_text_signature("resume", "jd changed")


def test_report_filename_has_no_personal_text() -> None:
    name = make_report_filename(datetime(2026, 10, 19, 12, 30, tzinfo=timezone.utc), "md")
    assert name.startswith("resume_match_report_20261019_")
    assert name.endswith(".md")
    with pytest.raises(ValueError, match="md 或 txt"):
        make_report_filename(datetime.now(timezone.utc), "pdf")
