"""将匹配结果和证据化建议导出为 Markdown 或纯文本报告。"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

from models.suggestion import ResumeSuggestion


@dataclass(frozen=True, slots=True)
class AnalysisReportData:
    """不包含完整简历正文的报告数据。"""

    generated_at: datetime
    scores: dict[str, float | None]
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]
    matched_experience: tuple[str, ...]
    missing_experience: tuple[str, ...]
    suggestions: tuple[ResumeSuggestion, ...]
    weights: tuple[float, float, float] | None
    weight_source: str


def build_text_signature(resume_text: str, jd_text: str) -> str:
    """建立文本组合摘要，用于阻止旧分析结果误配到新文本。"""
    payload = f"{resume_text}\0{jd_text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _score_text(value: float | None) -> str:
    return "未计算" if value is None else f"{value * 100:.2f}%"


def _items_text(items: tuple[str, ...]) -> str:
    return "、".join(items) if items else "无"


def render_markdown_report(data: AnalysisReportData) -> str:
    """生成结构化 Markdown 报告。"""
    lines = [
        "# 智能简历岗位匹配分析报告",
        "",
        f"- 生成时间：{data.generated_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %z')}",
        "- 数据说明：报告只包含匹配结果，不附带完整简历或 JD 正文。",
        "",
        "## 一、各项得分",
        "",
    ]
    labels = (
        ("TF-IDF 文本匹配度", "tfidf"),
        ("BGE 语义匹配度", "semantic"),
        ("技能覆盖率", "skill"),
        ("经历关键词覆盖率", "experience"),
        ("融合评分", "fusion"),
    )
    lines.extend(f"- {label}：{_score_text(data.scores.get(key))}" for label, key in labels)
    lines.extend(
        [
            "",
            "## 二、技能差距",
            "",
            f"- 已匹配技能：{_items_text(data.matched_skills)}",
            f"- 缺失技能：{_items_text(data.missing_skills)}",
            "",
            "## 三、经历关键词",
            "",
            f"- 已覆盖：{_items_text(data.matched_experience)}",
            f"- 未覆盖：{_items_text(data.missing_experience)}",
            "- 工作年限：未识别；本项目不从含糊文本推断工作年限。",
            "",
            "## 四、优化建议",
            "",
        ]
    )
    for index, suggestion in enumerate(data.suggestions, start=1):
        lines.extend(
            [
                f"### {index}. {suggestion.title}（{suggestion.priority}优先级）",
                "",
                suggestion.action,
                "",
                f"依据：{suggestion.basis}",
                "",
            ]
        )

    lines.extend(["## 五、算法说明", ""])
    if data.weights is not None:
        semantic, skill, experience = data.weights
        lines.append(
            f"- 融合公式：S = {semantic:.2f} × 语义分 + {skill:.2f} × 技能分 + {experience:.2f} × 经历分。"
        )
    else:
        lines.append("- 本次未生成融合评分。")
    lines.extend(
        [
            f"- 权重来源：{data.weight_source}",
            "- TF-IDF 衡量词项相似度；BGE 衡量语义向量相似度。",
            "- 技能和经历分数均为词典覆盖率，只反映文本中明确出现的证据。",
            "- 本报告不等同于录用概率、能力鉴定或招聘决定。",
            "- 建议由确定性规则与模板生成，不调用大语言模型 API，也不会自动补写不存在的经历或技能。",
            "",
        ]
    )
    return "\n".join(lines)


def render_text_report(data: AnalysisReportData) -> str:
    """从同一报告数据生成便于纯文本阅读的版本。"""
    markdown = render_markdown_report(data)
    text = re.sub(r"^#{1,6}\s*", "", markdown, flags=re.MULTILINE)
    text = re.sub(r"^-\s+", "• ", text, flags=re.MULTILINE)
    return text


def make_report_filename(generated_at: datetime, extension: str) -> str:
    """生成不含个人信息的报告文件名。"""
    clean_extension = extension.lower().lstrip(".")
    if clean_extension not in {"md", "txt"}:
        raise ValueError("报告扩展名只支持 md 或 txt。")
    return f"resume_match_report_{generated_at.astimezone().strftime('%Y%m%d_%H%M%S')}.{clean_extension}"
