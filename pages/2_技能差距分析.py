"""独立的技能差距分析页面。"""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.skill_extractor import SkillExtraction, analyze_skill_gap


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_style() -> None:
    """复用主页面样式。"""
    style_path = PROJECT_ROOT / "assets" / "style.css"
    if style_path.exists():
        st.markdown(f"<style>{style_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def render_tags(title: str, skills: tuple[str, ...], css_class: str, empty_text: str) -> None:
    """将词典中的标准技能名渲染为颜色标签。"""
    st.markdown(f"#### {title}")
    if not skills:
        st.caption(empty_text)
        return
    tags = "".join(
        f'<span class="skill-tag {css_class}">{html.escape(skill)}</span>' for skill in skills
    )
    st.markdown(f'<div class="skill-tags">{tags}</div>', unsafe_allow_html=True)


def evidence_rows(source: str, extraction: SkillExtraction) -> list[dict[str, str]]:
    """将归一化命中证据整理成可读表格。"""
    return [
        {
            "来源": source,
            "标准技能": skill,
            "命中表达": "、".join(extraction.evidence[skill]),
            "类别": extraction.categories[skill],
        }
        for skill in extraction.skills
    ]


def main() -> None:
    """渲染技能覆盖率、差距标签和归一化证据。"""
    st.set_page_config(page_title="技能差距分析", page_icon="🧩", layout="wide")
    load_style()

    st.title("技能差距分析")
    st.caption("基于版本化技能词典和同义词归一化；仅分析文本中明确出现的技能。")

    if "skill_resume_text" not in st.session_state:
        st.session_state["skill_resume_text"] = st.session_state.get("resume_text", "")
    if "skill_jd_text" not in st.session_state:
        st.session_state["skill_jd_text"] = st.session_state.get("jd_text", "")

    left, right = st.columns(2, gap="large")
    with left:
        resume_text = st.text_area(
            "简历文本",
            key="skill_resume_text",
            height=260,
            placeholder="可先在主页面上传简历，也可直接粘贴文本。",
        )
    with right:
        jd_text = st.text_area(
            "岗位 JD",
            key="skill_jd_text",
            height=260,
            placeholder="请粘贴包含岗位技能要求的 JD。",
        )

    if st.button("分析技能差距", type="primary", use_container_width=True):
        if not resume_text.strip() or not jd_text.strip():
            st.warning("请同时提供简历文本和岗位 JD。")
            return

        analysis = analyze_skill_gap(resume_text, jd_text)
        metrics = st.columns(4)
        if analysis.jd.skills:
            metrics[0].metric("岗位技能覆盖率", f"{analysis.coverage_rate * 100:.2f}%")
        else:
            metrics[0].metric("岗位技能覆盖率", "未识别")
        metrics[1].metric("简历技能数", len(analysis.resume.skills))
        metrics[2].metric("岗位技能数", len(analysis.jd.skills))
        metrics[3].metric("缺失技能数", len(analysis.missing_skills))

        if not analysis.jd.skills:
            st.warning("JD 未命中当前技能词典，无法计算有意义的覆盖率。可在 data/skills.json 中扩展词典。")

        first, second, third = st.columns(3)
        with first:
            render_tags("已匹配技能", analysis.matched_skills, "skill-tag--matched", "暂无共同技能")
        with second:
            render_tags("缺失技能", analysis.missing_skills, "skill-tag--missing", "暂无词典内缺失技能")
        with third:
            render_tags("简历额外技能", analysis.extra_skills, "skill-tag--extra", "暂无额外技能")

        rows = evidence_rows("简历", analysis.resume) + evidence_rows("岗位 JD", analysis.jd)
        st.subheader("同义词归一化证据")
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("简历和 JD 均未命中当前技能词典。")

        st.info(
            "覆盖率 = 已匹配的岗位技能数 ÷ JD 中识别出的技能数。"
            "词典匹配不推断熟练度、项目深度或隐含能力，也不构成招聘结论。"
        )


main()
