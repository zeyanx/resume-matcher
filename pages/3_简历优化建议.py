"""规则驱动的简历优化建议、报告导出与自愿满意度反馈页面。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st

from models.experience_matcher import calculate_experience_match
from models.suggestion import generate_resume_suggestions
from models.suggestion_policy import load_suggestion_policy
from models.tfidf_matcher import calculate_tfidf_similarity
from utils.feedback_config import FeedbackSettings, load_feedback_settings
from utils.feedback_store import (
    FeedbackStore,
    FeedbackStoreError,
    SuggestionFeedbackSubmission,
)
from utils.report_exporter import (
    AnalysisReportData,
    build_text_signature,
    make_report_filename,
    render_markdown_report,
    render_text_report,
)
from utils.skill_extractor import analyze_skill_gap


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@st.cache_resource(show_spinner=False)
def get_feedback_store(database_url: str, retention_days: int) -> FeedbackStore:
    store = FeedbackStore(database_url, retention_days=retention_days)
    store.initialize()
    return store


def get_feedback_settings() -> FeedbackSettings:
    try:
        return load_feedback_settings(st.secrets)
    except (FileNotFoundError, RuntimeError):
        return load_feedback_settings()


def load_style() -> None:
    style_path = PROJECT_ROOT / "assets" / "style.css"
    if style_path.exists():
        st.markdown(f"<style>{style_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def sync_main_text() -> None:
    st.session_state["optimization_resume_text"] = st.session_state.get("resume_text", "")
    st.session_state["optimization_jd_text"] = st.session_state.get("jd_text", "")


def generate_analysis(resume_text: str, jd_text: str) -> dict[str, object]:
    tfidf_score = calculate_tfidf_similarity(resume_text, jd_text)
    skill_analysis = analyze_skill_gap(resume_text, jd_text)
    experience_analysis = calculate_experience_match(resume_text, jd_text)
    policy = load_suggestion_policy()
    suggestions = generate_resume_suggestions(
        resume_text,
        jd_text,
        skill_analysis,
        experience_analysis,
        kind_weights=policy.kind_weights,
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
    return {
        "text_signature": current_signature,
        "generated_at": generated_at,
        "suggestions": suggestions,
        "scores": scores,
        "skill_coverage": skill_analysis.coverage_rate if skill_analysis.jd.skills else None,
        "experience_score": experience_analysis.score if experience_analysis.is_available else None,
        "missing_skill_count": len(skill_analysis.missing_skills),
        "missing_experience_count": len(experience_analysis.missing_keywords),
        "markdown_report": render_markdown_report(report_data),
        "text_report": render_text_report(report_data),
        "policy": policy,
        "reused_main_scores": latest_is_current,
    }


def render_suggestion_feedback(
    analysis: dict[str, object], resume_text: str, jd_text: str
) -> None:
    suggestions = analysis["suggestions"]
    policy = analysis["policy"]
    settings = get_feedback_settings()
    st.divider()
    st.subheader("建议满意度反馈")
    st.caption(
        "评分不会立即改变建议。反馈先进入待审核状态；至少 30 条合格记录、保留独立测试集并人工发布后，"
        "学习到的策略才会调整后续建议顺序。"
    )
    if not settings.enabled:
        st.info(
            "当前部署尚未配置持久化反馈数据库或隐私联系人，因此可以查看评分表，但暂不能提交。"
        )
    titles = [item.title for item in suggestions]
    with st.form("suggestion_feedback_form", clear_on_submit=False):
        satisfaction = st.slider("你对本次简历修改建议的满意度", 1, 5, 3)
        helpful_titles = st.multiselect(
            "哪些建议对你有帮助（可多选，也可不选）",
            options=titles,
        )
        comment = st.text_area(
            "补充意见（可选，请勿填写姓名、电话、邮箱等个人信息）",
            max_chars=2000,
            key="suggestion_feedback_comment",
        )
        consent = st.checkbox(
            "我同意保存满意度、所选建议类别、派生特征和经脱敏的补充意见，用于人工审核后的建议排序学习。"
        )
        research_text_consent = False
        if settings.allow_research_text:
            research_text_consent = st.checkbox(
                "另外同意保存经自动脱敏的简历与 JD 文本用于研究改进（可选，默认不勾选）。"
            )
        submitted = st.form_submit_button(
            "提交建议反馈",
            type="primary",
            use_container_width=True,
            disabled=not settings.enabled,
        )
    if not submitted:
        return
    if not consent:
        st.warning("请先阅读并勾选数据使用同意项。")
        return
    title_to_kind = {item.title: item.kind for item in suggestions}
    try:
        store = get_feedback_store(settings.database_url, settings.retention_days)
        store.purge_expired()
        receipt = store.submit_suggestion_feedback(
            SuggestionFeedbackSubmission(
                satisfaction_rating=int(satisfaction),
                suggestion_kinds=[item.kind for item in suggestions],
                suggestion_priorities=[item.priority for item in suggestions],
                helpful_kinds=[title_to_kind[title] for title in helpful_titles],
                feedback_comment=comment,
                skill_coverage=analysis["skill_coverage"],
                experience_score=analysis["experience_score"],
                missing_skill_count=int(analysis["missing_skill_count"]),
                missing_experience_count=int(analysis["missing_experience_count"]),
                resume_length=len(resume_text),
                jd_length=len(jd_text),
                suggestion_policy_version=policy.version,
                policy_consent=True,
                research_text_consent=research_text_consent,
                resume_text=resume_text,
                jd_text=jd_text,
                consent_version=settings.consent_version,
            )
        )
    except FeedbackStoreError as exc:
        st.error(str(exc))
    else:
        st.success("建议反馈已保存为待人工审核记录，不会立即改变线上建议。")
        st.code(receipt.deletion_token, language=None)
        st.warning("请立即保存上方删除码；系统仅保存其哈希值，丢失后无法找回。")
        st.caption(f"记录编号：{receipt.submission_id}；数据切分：{receipt.split}。")


def main() -> None:
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

    if st.button("生成优化建议与报告", type="primary", use_container_width=True):
        if not resume_text.strip() or not jd_text.strip():
            st.warning("请同时提供简历文本和岗位 JD。")
        else:
            try:
                st.session_state["latest_suggestion_analysis"] = generate_analysis(
                    resume_text, jd_text
                )
            except ValueError as exc:
                st.warning(str(exc))

    analysis = st.session_state.get("latest_suggestion_analysis")
    current_signature = (
        build_text_signature(resume_text, jd_text)
        if resume_text.strip() and jd_text.strip()
        else ""
    )
    if not analysis or analysis.get("text_signature") != current_signature:
        st.info("准备好简历和 JD 后点击生成。若要包含 BGE 与融合分，请先在主页面完成一次匹配。")
        return
    if not analysis["reused_main_scores"]:
        st.warning("当前文本与主页面最近一次分析不一致，因此报告不复用旧的 BGE 与融合分。")

    policy = analysis["policy"]
    if policy.status == "approved" and policy.kind_weights:
        st.caption(f"建议顺序使用已发布满意度学习策略：{policy.version}（{policy.learned_from} 条已审核反馈）。")
    else:
        st.caption("建议顺序使用规则基线；目前没有足够的已审核满意度反馈可发布学习策略。")

    st.subheader("优化建议")
    for index, suggestion in enumerate(analysis["suggestions"], start=1):
        with st.container(border=True):
            st.markdown(f"#### {index}. {suggestion.title}")
            st.write(suggestion.action)
            st.caption(f"{suggestion.priority}优先级 · 依据：{suggestion.basis}")

    st.subheader("报告预览")
    with st.expander("查看 Markdown 报告内容"):
        st.markdown(analysis["markdown_report"])
    download_left, download_right = st.columns(2)
    generated_at = analysis["generated_at"]
    download_left.download_button(
        "下载 Markdown 报告",
        data=analysis["markdown_report"].encode("utf-8"),
        file_name=make_report_filename(generated_at, "md"),
        mime="text/markdown; charset=utf-8",
        use_container_width=True,
    )
    download_right.download_button(
        "下载 TXT 报告",
        data=analysis["text_report"].encode("utf-8-sig"),
        file_name=make_report_filename(generated_at, "txt"),
        mime="text/plain; charset=utf-8",
        use_container_width=True,
    )
    st.caption("导出报告不包含完整简历或 JD 正文，减少不必要的个人信息复制。")
    render_suggestion_feedback(analysis, resume_text, jd_text)


main()
