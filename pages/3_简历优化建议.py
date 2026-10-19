"""规则驱动的简历优化建议和分析报告导出页面。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from models.experience_matcher import calculate_experience_match
from models.suggestion import generate_resume_suggestions
from models.tfidf_matcher import calculate_tfidf_similarity
from utils.report_exporter import (
    AnalysisReportData,
    build_text_signature,
    make_report_filename,
    render_markdown_report,
    render_text_report,
)
from utils.skill_extractor import analyze_skill_gap


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_style() -> None:
    """复用主页面样式。"""
    style_path = PROJECT_ROOT / "assets" / "style.css"
    if style_path.exists():
        st.markdown(f"<style>{style_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def sync_main_text() -> None:
    """按用户操作把主页面最新文本同步到本页。"""
    st.session_state["optimization_resume_text"] = st.session_state.get("resume_text", "")
    st.session_state["optimization_jd_text"] = st.session_state.get("jd_text", "")


def main() -> None:
    """生成证据化建议，并提供 Markdown/TXT 下载。"""
    st.set_page_config(page_title="简历优化建议", page_icon="📝", layout="wide")
    load_style()
    st.title("简历优化建议与报告导出")
    st.caption("建议由规则、技能差距和模板生成，不调用大语言模型，也不会自动补写不存在的经历。")

    if "optimization_resume_text" not in st.session_state:
        st.session_state["optimization_resume_text"] = st.session_state.get("resume_text", "")
    if "optimization_jd_text" not in st.session_state:
        st.session_state["optimization_jd_text"] = st.session_state.get("jd_text", "")

    st.button("从主页面同步最新文本", on_click=sync_main_text)
    left, right = st.columns(2, gap="large")
    with left:
        resume_text = st.text_area(
            "简历文本",
            key="optimization_resume_text",
            height=240,
            placeholder="可从主页面同步，或直接粘贴简历文本。",
        )
    with right:
        jd_text = st.text_area(
            "岗位 JD",
            key="optimization_jd_text",
            height=240,
            placeholder="可从主页面同步，或直接粘贴岗位描述。",
        )

    if not st.button("生成优化建议与报告", type="primary", use_container_width=True):
        st.info("准备好简历和 JD 后点击生成。若要包含 BGE 与融合分，请先在主页面完成一次匹配。")
        return
    if not resume_text.strip() or not jd_text.strip():
        st.warning("请同时提供简历文本和岗位 JD。")
        return

    try:
        tfidf_score = calculate_tfidf_similarity(resume_text, jd_text)
    except ValueError as exc:
        st.warning(str(exc))
        return

    skill_analysis = analyze_skill_gap(resume_text, jd_text)
    experience_analysis = calculate_experience_match(resume_text, jd_text)
    suggestions = generate_resume_suggestions(
        resume_text,
        jd_text,
        skill_analysis,
        experience_analysis,
    )

    current_signature = build_text_signature(resume_text, jd_text)
    latest = st.session_state.get("latest_analysis", {})
    latest_is_current = latest.get("text_signature") == current_signature
    scores = {
        "tfidf": tfidf_score,
        "semantic": None,
        "skill": skill_analysis.coverage_rate if skill_analysis.jd.skills else None,
        "experience": experience_analysis.score if experience_analysis.is_available else None,
        "fusion": None,
    }
    weights = None
    weight_source = "本页未加载 BGE；请先在主页面对相同文本完成匹配"
    if latest_is_current:
        latest_scores = latest.get("scores", {})
        scores["semantic"] = latest_scores.get("semantic")
        scores["fusion"] = latest_scores.get("fusion")
        weights = latest.get("weights")
        weight_source = latest.get("weight_source", "未注明")
    else:
        st.warning("当前文本与主页面最近一次分析不一致，因此报告不复用旧的 BGE 与融合分。")

    st.subheader("优化建议")
    for index, suggestion in enumerate(suggestions, start=1):
        with st.container(border=True):
            st.markdown(f"#### {index}. {suggestion.title}")
            st.write(suggestion.action)
            st.caption(f"{suggestion.priority}优先级 · 依据：{suggestion.basis}")

    generated_at = datetime.now().astimezone()
    report_data = AnalysisReportData(
        generated_at=generated_at,
        scores=scores,
        matched_skills=skill_analysis.matched_skills,
        missing_skills=skill_analysis.missing_skills,
        matched_experience=experience_analysis.matched_keywords,
        missing_experience=experience_analysis.missing_keywords,
        suggestions=suggestions,
        weights=tuple(weights) if weights is not None else None,
        weight_source=str(weight_source),
    )
    markdown_report = render_markdown_report(report_data)
    text_report = render_text_report(report_data)

    st.subheader("报告预览")
    with st.expander("查看 Markdown 报告内容"):
        st.markdown(markdown_report)

    download_left, download_right = st.columns(2)
    download_left.download_button(
        "下载 Markdown 报告",
        data=markdown_report.encode("utf-8"),
        file_name=make_report_filename(generated_at, "md"),
        mime="text/markdown; charset=utf-8",
        use_container_width=True,
    )
    download_right.download_button(
        "下载 TXT 报告",
        data=text_report.encode("utf-8-sig"),
        file_name=make_report_filename(generated_at, "txt"),
        mime="text/plain; charset=utf-8",
        use_container_width=True,
    )
    st.caption("导出报告不包含完整简历或 JD 正文，减少不必要的个人信息复制。")


main()
