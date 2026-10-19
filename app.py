"""ResumeMatcher 最终版：匹配、建议、报告、评估与可视化。"""

import csv
import json
from pathlib import Path
import time

import plotly.graph_objects as go
import streamlit as st

from models.bge_matcher import BGEModelError, calculate_bge_similarity, load_bge_model
from models.experience_matcher import calculate_experience_match
from models.fusion_matcher import (
    FusionConfigError,
    FusionWeights,
    calculate_fusion_score,
    load_fusion_weight_config,
)
from models.tfidf_matcher import calculate_tfidf_similarity
from utils.feedback_config import FeedbackSettings, load_feedback_settings
from utils.feedback_store import FeedbackStore, FeedbackStoreError, FeedbackSubmission
from utils.faircv import FairCVError, fetch_faircv_rows
from utils.resume_parser import ResumeParseError, parse_resume_bytes
from utils.report_exporter import build_text_signature
from utils.skill_extractor import analyze_skill_gap


PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLE_RESUME_PATH = PROJECT_ROOT / "data" / "sample_resumes" / "sample_resume.txt"
SAMPLE_JD_PATH = PROJECT_ROOT / "data" / "sample_jds" / "sample_python_backend.txt"
FAIRCV_EXAMPLES_PATH = PROJECT_ROOT / "data" / "sample_resumes" / "faircv_examples.json"
TEST_CASES_PATH = PROJECT_ROOT / "data" / "test_cases.csv"
BGE_CACHE_DIR = PROJECT_ROOT / "models_cache" / "huggingface"
LOCAL_BGE_MODEL_DIR = PROJECT_ROOT / "models_cache" / "bge-small-zh-v1.5"
DEFAULT_LOCAL_BGE_PATH = str(LOCAL_BGE_MODEL_DIR) if LOCAL_BGE_MODEL_DIR.is_dir() else ""
DEFAULT_FUSION_CONFIG = load_fusion_weight_config()


@st.cache_resource(show_spinner=False)
def get_cached_bge_model(local_model_path: str, offline: bool):
    """按模型路径和离线开关缓存 BGE 模型，避免页面重跑时重复加载。"""
    return load_bge_model(
        local_model_path=local_model_path or None,
        cache_folder=str(BGE_CACHE_DIR),
        offline=offline,
    )


@st.cache_resource(show_spinner=False)
def get_feedback_store(database_url: str, retention_days: int) -> FeedbackStore:
    """缓存数据库连接池；数据库密钥不会显示在页面中。"""
    store = FeedbackStore(database_url, retention_days=retention_days)
    store.initialize()
    return store


def get_feedback_settings() -> FeedbackSettings:
    """安全读取 Streamlit secrets；本地没有 secrets 文件时保持禁用。"""
    try:
        secrets = st.secrets
        return load_feedback_settings(secrets)
    except (FileNotFoundError, RuntimeError):
        return load_feedback_settings()


def render_feedback_section(resume_text: str, jd_text: str) -> None:
    """仅在当前文本已有匹配结果时显示自愿反馈表。"""
    analysis = st.session_state.get("latest_analysis")
    if not analysis or analysis.get("text_signature") != build_text_signature(resume_text, jd_text):
        return

    settings = get_feedback_settings()
    st.divider()
    st.subheader("4. 自愿反馈与数据改进")
    if not settings.enabled:
        st.info(
            "当前部署未启用数据收集，简历和 JD 不会写入反馈数据库。"
            "管理员配置数据库、隐私联系人并显式开启后，用户才可主动提交反馈。"
        )
        return

    st.caption(
        "匹配计算本身不会保存输入。只有点击“提交反馈”并勾选同意后才会保存反馈；"
        f"最长保留 {settings.retention_days} 天。"
    )
    with st.form("match_feedback_form", clear_on_submit=False):
        relevance_label = st.radio(
            "你认为这份简历与岗位的实际匹配程度",
            options=[0, 1, 2, 3],
            format_func=lambda value: {
                0: "0 · 不匹配",
                1: "1 · 较弱",
                2: "2 · 较匹配",
                3: "3 · 高度匹配",
            }[value],
            horizontal=True,
        )
        helpfulness_rating = st.slider("本次结果对你有多大帮助", 1, 5, 3)
        feedback_comment = st.text_area(
            "补充意见（可选，请勿填写姓名、电话、邮箱等个人信息）",
            max_chars=2000,
        )
        policy_consent = st.checkbox(
            "我同意保存本次评分、模型子分数、技能命中结果和经脱敏的补充意见，用于人工审核后的模型评估。"
        )
        research_text_consent = False
        if settings.allow_research_text:
            research_text_consent = st.checkbox(
                "另外同意保存经自动脱敏的简历与 JD 文本，用于研究改进（可选，默认不勾选）。"
            )
            st.caption("自动脱敏不能保证识别全部个人信息；若不确定，请勿勾选此项。")
        submitted = st.form_submit_button("提交反馈", type="primary", use_container_width=True)

    if submitted:
        if not policy_consent:
            st.warning("请先阅读并勾选数据使用同意项。")
            return
        try:
            store = get_feedback_store(settings.database_url, settings.retention_days)
            store.purge_expired()
            receipt = store.submit(
                FeedbackSubmission(
                    relevance_label=int(relevance_label),
                    helpfulness_rating=int(helpfulness_rating),
                    feedback_comment=feedback_comment,
                    scores=analysis["scores"],
                    matched_skills=analysis["matched_skills"],
                    missing_skills=analysis["missing_skills"],
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
            st.success("反馈已保存为待人工审核记录。它不会立即改变线上模型。")
            st.code(receipt.deletion_token, language=None)
            st.warning("请立即保存上方删除码。系统只保存它的哈希值，丢失后无法找回。")
            st.caption(f"记录编号：{receipt.submission_id}；数据切分：{receipt.split}。")


def load_style() -> None:
    """加载项目自己的少量页面样式；样式缺失时不影响核心功能。"""
    style_path = PROJECT_ROOT / "assets" / "style.css"
    if style_path.exists():
        st.markdown(f"<style>{style_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def load_example_catalog() -> tuple[dict[str, object], ...]:
    """读取仅含 FairCV 源行号和展示元数据的示例目录。"""
    if not FAIRCV_EXAMPLES_PATH.is_file():
        return ()
    payload = json.loads(FAIRCV_EXAMPLES_PATH.read_text(encoding="utf-8"))
    return tuple(item for item in payload if isinstance(item, dict))


@st.cache_data(show_spinner=False, ttl=24 * 60 * 60)
def fetch_example_resume(row_index: int) -> str:
    """按源行号读取 FairCV，并沿用受保护字段移除逻辑。"""
    last_error: Exception | None = None
    batch = None
    for attempt in range(3):
        try:
            batch = fetch_faircv_rows(offset=row_index, length=1, timeout_seconds=20)
            break
        except FairCVError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    if batch is None:
        raise FairCVError("FairCV 示例连续读取失败，请稍后重试。") from last_error
    if not batch.records or batch.records[0].row_index != row_index:
        raise FairCVError("FairCV 示例行未返回预期记录。")
    return batch.records[0].matching_text


def find_example_jd(jd_id: str) -> str:
    """从固定测试集找到示例对应的公开 JD。"""
    if not TEST_CASES_PATH.is_file():
        return SAMPLE_JD_PATH.read_text(encoding="utf-8")
    with TEST_CASES_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("jd_id") == jd_id:
                return row.get("jd_text", "").strip()
    return SAMPLE_JD_PATH.read_text(encoding="utf-8")


def load_example(example: dict[str, object] | None = None) -> None:
    """将 FairCV 合成简历和对应公开 JD 载入会话状态。"""
    if example is None:
        st.session_state["resume_text"] = SAMPLE_RESUME_PATH.read_text(encoding="utf-8")
        st.session_state["jd_text"] = SAMPLE_JD_PATH.read_text(encoding="utf-8")
    else:
        resume = fetch_example_resume(int(example["source_row_index"]))
        st.session_state["resume_text"] = resume
        st.session_state["jd_text"] = find_example_jd(str(example["default_jd_id"]))
    st.session_state.pop("resume_file_info", None)


def main() -> None:
    """渲染支持 PDF、DOCX、TXT 的简历匹配页面。"""
    st.set_page_config(page_title="智能简历岗位匹配", page_icon="📄", layout="wide")
    load_style()

    st.title("智能简历岗位匹配系统")
    st.caption("最终工程 · 多维匹配 + 证据化建议 + 可复现评估与可视化")

    with st.sidebar:
        st.subheader("演示说明")
        st.write(
            "支持 PDF、DOCX、TXT。匹配时内容仅在当前会话中处理；"
            "只有用户在反馈区单独明确授权后，才可能保存脱敏文本。"
        )
        examples = load_example_catalog()
        if examples:
            selected_example = st.selectbox(
                "FairCV 合成示例",
                options=examples,
                format_func=lambda item: str(item.get("label", item.get("id", "示例"))),
            )
            if st.button("加载示例简历与 JD", use_container_width=True):
                try:
                    with st.spinner("正在读取 FairCV 合成示例……"):
                        load_example(selected_example)
                except (FairCVError, OSError, ValueError) as exc:
                    load_example()
                    st.warning(f"FairCV 暂时不可用，已加载内置离线示例：{exc}")
                else:
                    st.success("已加载合成简历与公开 JD。")
            st.button("载入内置离线示例", on_click=load_example, use_container_width=True)
        else:
            st.button("载入内置离线示例", on_click=load_example, use_container_width=True)
        st.caption("示例简历来自 FairCV 合成数据，仅用于课程演示，不代表真实求职者。")
        st.divider()
        st.subheader("BGE 模型")
        enable_bge = st.toggle("启用 BGE 语义匹配", value=True)
        local_model_path = st.text_input(
            "本地模型目录（可选）",
            value=DEFAULT_LOCAL_BGE_PATH,
            placeholder="例如 models_cache/bge-small-zh-v1.5",
            help="留空时使用 BAAI/bge-small-zh-v1.5，首次运行需要联网下载。",
        )
        offline_mode = st.toggle(
            "仅使用本地文件",
            value=bool(DEFAULT_LOCAL_BGE_PATH),
            help="启用后禁止联网；必须已有完整缓存或指定本地模型目录。",
        )
        st.divider()
        st.subheader("融合权重")
        semantic_weight = st.number_input(
            "语义权重 α",
            min_value=0.0,
            max_value=1.0,
            value=DEFAULT_FUSION_CONFIG.weights.semantic,
            step=0.05,
        )
        skill_weight = st.number_input(
            "技能权重 β",
            min_value=0.0,
            max_value=1.0,
            value=DEFAULT_FUSION_CONFIG.weights.skill,
            step=0.05,
        )
        experience_weight = st.number_input(
            "经历权重 γ",
            min_value=0.0,
            max_value=1.0,
            value=DEFAULT_FUSION_CONFIG.weights.experience,
            step=0.05,
        )
        st.caption(
            f"权重和：{semantic_weight + skill_weight + experience_weight:.2f}；"
            f"来源：{DEFAULT_FUSION_CONFIG.source}。"
        )

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("1. 输入简历")
        uploaded_file = st.file_uploader("上传简历", type=["pdf", "docx", "txt"])
        if uploaded_file is not None:
            try:
                parsed_resume = parse_resume_bytes(uploaded_file.getvalue(), uploaded_file.name)
                st.session_state["resume_text"] = parsed_resume.text
                st.session_state["resume_file_info"] = parsed_resume
            except ResumeParseError as exc:
                st.session_state.pop("resume_file_info", None)
                st.error(str(exc))

        parsed_info = st.session_state.get("resume_file_info")
        if parsed_info is not None:
            details = f"已解析 {parsed_info.file_type} · {parsed_info.character_count:,} 个字符"
            if parsed_info.page_count is not None:
                details += f" · {parsed_info.page_count} 页"
            st.success(details)

        resume_text = st.text_area(
            "解析后的简历文本（可人工修正）",
            key="resume_text",
            height=320,
            placeholder="请上传 PDF、DOCX、TXT 简历，或在此粘贴简历内容。",
        )

    with right:
        st.subheader("2. 输入岗位 JD")
        jd_text = st.text_area(
            "岗位描述",
            key="jd_text",
            height=384,
            placeholder="请粘贴岗位职责、任职要求和技能要求。",
        )

    st.subheader("3. 计算匹配度")
    if st.button("开始匹配", type="primary", use_container_width=True):
        try:
            tfidf_score = calculate_tfidf_similarity(resume_text, jd_text)
        except ValueError as exc:
            st.warning(str(exc))
        else:
            skill_analysis = analyze_skill_gap(resume_text, jd_text)
            experience_analysis = calculate_experience_match(resume_text, jd_text)
            semantic_result = None
            semantic_error = None
            model_device = None
            if enable_bge:
                try:
                    with st.spinner("正在加载 BGE 模型并计算语义匹配度……"):
                        bge_model = get_cached_bge_model(local_model_path.strip(), offline_mode)
                        model_device = str(getattr(bge_model, "device", "未知设备"))
                        semantic_result = calculate_bge_similarity(
                            resume_text,
                            jd_text,
                            bge_model,
                        )
                except (BGEModelError, ValueError) as exc:
                    semantic_error = str(exc)

            fusion_result = None
            fusion_error = None
            selected_weights = None
            try:
                selected_weights = FusionWeights(
                    semantic=float(semantic_weight),
                    skill=float(skill_weight),
                    experience=float(experience_weight),
                )
                if semantic_result is None:
                    fusion_error = "需要可用的 BGE 语义分数"
                elif not skill_analysis.jd.skills:
                    fusion_error = "JD 未识别出技能"
                elif not experience_analysis.is_available:
                    fusion_error = "JD 未识别出经历或职责关键词"
                else:
                    fusion_result = calculate_fusion_score(
                        semantic_result.score,
                        skill_analysis.coverage_rate,
                        experience_analysis.score,
                        selected_weights,
                    )
            except FusionConfigError as exc:
                fusion_error = str(exc)

            metric_tfidf, metric_bge, metric_skill, metric_experience, metric_fusion = st.columns(5)
            metric_tfidf.metric("TF-IDF", f"{tfidf_score * 100:.2f}%")
            if semantic_result is not None:
                metric_bge.metric("BGE 语义", f"{semantic_result.score * 100:.2f}%")
                st.caption(
                    f"BGE 设备：{model_device}；简历分块 {semantic_result.resume_chunks} 个，"
                    f"JD 分块 {semantic_result.jd_chunks} 个；原始余弦值 "
                    f"{semantic_result.raw_cosine:.4f}。"
                )
            elif semantic_error:
                metric_bge.metric("BGE 语义", "不可用")
                st.warning(f"BGE 暂不可用，本次已降级为 TF-IDF 基线。原因：{semantic_error}")
            else:
                metric_bge.metric("BGE 语义", "未启用")

            if skill_analysis.jd.skills:
                metric_skill.metric("技能覆盖", f"{skill_analysis.coverage_rate * 100:.2f}%")
                matched = "、".join(skill_analysis.matched_skills) or "无"
                missing = "、".join(skill_analysis.missing_skills) or "无"
                st.caption(f"技能概览：已匹配 {matched}；待补足 {missing}。完整证据见左侧“技能差距分析”页面。")
            else:
                metric_skill.metric("技能覆盖", "未识别")
                st.caption("当前 JD 未命中技能词典，因此不展示可能误导的技能覆盖率。")

            if experience_analysis.is_available:
                metric_experience.metric("经历关键词", f"{experience_analysis.score * 100:.2f}%")
                experience_matched = "、".join(experience_analysis.matched_keywords) or "无"
                experience_missing = "、".join(experience_analysis.missing_keywords) or "无"
                st.caption(
                    f"经历关键词：已覆盖 {experience_matched}；未覆盖 {experience_missing}；"
                    f"工作年限：{experience_analysis.years_status}。"
                )
            else:
                metric_experience.metric("经历关键词", "未识别")
                st.caption("当前 JD 未命中经历关键词词典；工作年限不做推断。")

            if fusion_result is not None:
                metric_fusion.metric("融合评分", f"{fusion_result.score * 100:.2f}%")
                st.caption(
                    "融合公式："
                    f"{selected_weights.semantic:.2f}×语义 + "
                    f"{selected_weights.skill:.2f}×技能 + "
                    f"{selected_weights.experience:.2f}×经历。"
                )
            else:
                metric_fusion.metric("融合评分", "不可用")
                st.caption(f"融合评分未计算：{fusion_error}。")

            weight_source = DEFAULT_FUSION_CONFIG.source
            if selected_weights is not None and selected_weights != DEFAULT_FUSION_CONFIG.weights:
                weight_source = f"当前会话手动设置；基础配置：{DEFAULT_FUSION_CONFIG.source}"
            st.session_state["latest_analysis"] = {
                "text_signature": build_text_signature(resume_text, jd_text),
                "scores": {
                    "tfidf": tfidf_score,
                    "semantic": semantic_result.score if semantic_result is not None else None,
                    "skill": (
                        skill_analysis.coverage_rate if skill_analysis.jd.skills else None
                    ),
                    "experience": (
                        experience_analysis.score if experience_analysis.is_available else None
                    ),
                    "fusion": fusion_result.score if fusion_result is not None else None,
                },
                "matched_skills": skill_analysis.matched_skills,
                "missing_skills": skill_analysis.missing_skills,
                "matched_experience": experience_analysis.matched_keywords,
                "missing_experience": experience_analysis.missing_keywords,
                "weights": (
                    (
                        selected_weights.semantic,
                        selected_weights.skill,
                        selected_weights.experience,
                    )
                    if selected_weights is not None
                    else None
                ),
                "weight_source": weight_source,
            }

            if semantic_result is not None and fusion_result is not None:
                chart_left, chart_right = st.columns(2, gap="large")
                with chart_left:
                    bar = go.Figure(
                        go.Bar(
                            x=["TF-IDF", "BGE", "融合评分"],
                            y=[tfidf_score * 100, semantic_result.score * 100, fusion_result.score * 100],
                            marker_color=["#7A8DA8", "#4C78A8", "#59A14F"],
                            text=[
                                f"{tfidf_score * 100:.2f}%",
                                f"{semantic_result.score * 100:.2f}%",
                                f"{fusion_result.score * 100:.2f}%",
                            ],
                            textposition="outside",
                        )
                    )
                    bar.update_layout(
                        title="算法结果对比",
                        yaxis_title="分数（%）",
                        yaxis_range=[0, 110],
                        margin=dict(l=20, r=20, t=55, b=20),
                        height=360,
                    )
                    st.plotly_chart(bar, use_container_width=True)
                with chart_right:
                    dimensions = ["语义", "技能", "经历", "关键词/TF-IDF"]
                    values = [
                        semantic_result.score * 100,
                        skill_analysis.coverage_rate * 100,
                        experience_analysis.score * 100,
                        tfidf_score * 100,
                    ]
                    radar = go.Figure(
                        go.Scatterpolar(
                            r=values + [values[0]],
                            theta=dimensions + [dimensions[0]],
                            fill="toself",
                            name="当前匹配",
                            line_color="#4C78A8",
                        )
                    )
                    radar.update_layout(
                        title="多维匹配雷达图",
                        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                        showlegend=False,
                        margin=dict(l=30, r=30, t=55, b=20),
                        height=360,
                    )
                    st.plotly_chart(radar, use_container_width=True)

            st.progress(tfidf_score)
            st.info(
                "当前分数用于文本匹配分析，不等同于录用概率。"
                "当前融合权重是未经真实人工标注验证的界面初始值，不是最优权重。"
            )

    render_feedback_section(resume_text, jd_text)


if __name__ == "__main__":
    main()
