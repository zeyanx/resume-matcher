"""基于可核查文本证据的简历优化建议，不调用大语言模型。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from models.experience_matcher import ExperienceMatchResult
from utils.skill_extractor import SkillGapAnalysis


@dataclass(frozen=True, slots=True)
class ResumeSuggestion:
    """一条包含依据和具体行动的建议。"""

    title: str
    action: str
    basis: str
    priority: str


def _join(items: tuple[str, ...], limit: int = 6) -> str:
    """限制展示项数量，避免建议过长。"""
    selected = items[:limit]
    suffix = "等" if len(items) > limit else ""
    return "、".join(selected) + suffix


def generate_resume_suggestions(
    resume_text: str,
    jd_text: str,
    skill_analysis: SkillGapAnalysis,
    experience_analysis: ExperienceMatchResult,
    minimum: int = 3,
    maximum: int = 5,
) -> tuple[ResumeSuggestion, ...]:
    """生成 3–5 条可操作建议，且不把缺失内容写成已有经历。"""
    if minimum < 1 or maximum < minimum:
        raise ValueError("建议数量范围无效。")

    suggestions: list[ResumeSuggestion] = []

    if skill_analysis.missing_skills:
        missing = _join(skill_analysis.missing_skills)
        suggestions.append(
            ResumeSuggestion(
                title="核对并处理岗位缺失技能",
                action=(
                    f"JD 提到 {missing}，当前简历未检出。若你确实使用过其中某项，请补充真实的项目、课程或工作证据；"
                    "若尚未掌握，应将其作为学习计划，不要直接写成已掌握技能。"
                ),
                basis=f"技能差距：{missing}",
                priority="高",
            )
        )

    if experience_analysis.missing_keywords:
        missing = _join(experience_analysis.missing_keywords)
        suggestions.append(
            ResumeSuggestion(
                title="补强与岗位职责对应的经历证据",
                action=(
                    f"JD 涉及 {missing}，当前简历没有对应关键词。若确有相关经历，可用“做了什么—如何完成—真实结果”补充一条；"
                    "如果没有，不要虚构，可保留为待提升方向。"
                ),
                basis=f"未覆盖的经历或职责关键词：{missing}",
                priority="高",
            )
        )

    if skill_analysis.jd.skills and skill_analysis.coverage_rate < 0.6:
        suggestions.append(
            ResumeSuggestion(
                title="优先呈现与目标岗位直接相关的技能",
                action=(
                    "当前词典内岗位技能覆盖率低于 60%。请将已经真实掌握、且与 JD 直接相关的技能放在技能区和对应项目描述的前部，"
                    "同时删除无法提供事实证据的空泛熟练度表述。"
                ),
                basis=f"岗位技能覆盖率：{skill_analysis.coverage_rate * 100:.2f}%",
                priority="高",
            )
        )

    section_names = ("教育", "技能", "项目", "工作", "实习")
    missing_sections = tuple(name for name in section_names if name not in resume_text)
    if len(missing_sections) >= 2:
        names = "、".join(missing_sections)
        suggestions.append(
            ResumeSuggestion(
                title="完善简历的信息结构",
                action=(
                    f"当前文本未明确识别到这些常见栏目：{names}。请按真实情况补充分区标题；"
                    "没有工作经历时可明确以课程项目、个人项目或实习准备为主，不需要编造栏目内容。"
                ),
                basis=f"未识别栏目：{names}",
                priority="中",
            )
        )

    if not re.search(r"\d|%|％", resume_text):
        suggestions.append(
            ResumeSuggestion(
                title="补充可核实的结果证据",
                action=(
                    "当前简历未检测到数字或比例。若有可核实记录，可补充真实的项目规模、响应时间、测试数量、效率变化或交付周期；"
                    "没有可靠数据时，用明确产出替代数字，不要估造指标。"
                ),
                basis="简历文本未检测到数字或百分比",
                priority="中",
            )
        )

    if experience_analysis.matched_keywords:
        matched = _join(experience_analysis.matched_keywords)
        suggestions.append(
            ResumeSuggestion(
                title="把已匹配职责写成证据链",
                action=(
                    f"当前已匹配 {matched}。建议在对应项目中写清个人动作、使用方法和可核实产出，"
                    "避免只罗列关键词。"
                ),
                basis=f"已覆盖的经历关键词：{matched}",
                priority="中",
            )
        )

    fallbacks = (
        ResumeSuggestion(
            title="统一岗位名称与求职意向",
            action="检查求职意向是否与当前 JD 的岗位方向一致，只调整真实求职方向，不修改或虚构既有经历。",
            basis="通用结构检查",
            priority="低",
        ),
        ResumeSuggestion(
            title="逐条校验技能证据",
            action="对技能区的每项技能，确认正文中至少有一处真实项目、课程或工作证据；无法说明使用场景的技能应谨慎保留。",
            basis="技能证据一致性检查",
            priority="中",
        ),
        ResumeSuggestion(
            title="压缩空泛自我评价",
            action="将无法验证的形容词替换为真实行动或产出；若没有相应事实，就保持简洁，不添加未经证实的能力。",
            basis="可验证性检查",
            priority="低",
        ),
    )
    existing_titles = {item.title for item in suggestions}
    for fallback in fallbacks:
        if len(suggestions) >= minimum:
            break
        if fallback.title not in existing_titles:
            suggestions.append(fallback)
            existing_titles.add(fallback.title)

    return tuple(suggestions[:maximum])
