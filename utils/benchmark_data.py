"""FairCV 简历与公开中文 JD 的评估数据准备工具。"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from utils.feedback_store import redact_personal_data


JD_DATASET_ID = "wangzihaogithub/job-educational-parser-dataset-08-0-0805"
JD_DATASET_PAGE = (
    "https://huggingface.co/datasets/"
    "wangzihaogithub/job-educational-parser-dataset-08-0-0805"
)
JD_SOURCE_FILE = "default/test/2w_0716.csv"
JD_SOURCE_URL = f"{JD_DATASET_PAGE}/resolve/main/{JD_SOURCE_FILE}?download=true"
JD_LICENSE = "Apache-2.0"

TITLE_RE = re.compile(r"<岗位名称>\s*(.*?)\s*</岗位名称>", re.DOTALL)
DESCRIPTION_RE = re.compile(r"<岗位描述>\s*(.*?)\s*</岗位描述>", re.DOTALL)
EDUCATION_RE = re.compile(r"<学历描述>\s*(.*?)\s*</学历描述>", re.DOTALL)
TAG_RE = re.compile(r"</?[^>]+>")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class JobDescriptionRecord:
    """一条可追溯的公开岗位描述。"""

    source_row_index: int
    source_job_id: str
    title: str
    description: str
    education: str

    @property
    def matching_text(self) -> str:
        education_line = f"\n学历要求：{self.education}" if self.education else ""
        return f"岗位名称：{self.title}\n岗位描述：{self.description}{education_line}".strip()


def _clean_fragment(value: str | None) -> str:
    text = TAG_RE.sub(" ", str(value or ""))
    return redact_personal_data(SPACE_RE.sub(" ", text).strip(" ,，;；"))


def parse_job_markup(value: str | None) -> tuple[str, str, str]:
    """从数据集的 XML 风格文本中分离岗位名、描述和学历要求。"""
    text = str(value or "").strip()
    title_match = TITLE_RE.search(text)
    descriptions = DESCRIPTION_RE.findall(text)
    education_match = EDUCATION_RE.search(text)
    title = _clean_fragment(title_match.group(1)) if title_match else ""
    description = " ".join(
        part for part in (_clean_fragment(item) for item in descriptions) if part
    )
    education = _clean_fragment(education_match.group(1)) if education_match else ""
    if not description:
        description = _clean_fragment(text)
    if not title:
        prefix = text.split("<岗位描述>", 1)[0]
        title = _clean_fragment(prefix)
    return title, description, education


def load_job_descriptions(
    path: str | Path,
    *,
    minimum_characters: int = 80,
    maximum_characters: int = 5000,
) -> tuple[JobDescriptionRecord, ...]:
    """读取原始 UTF-8 CSV，过滤过短、过长和重复的岗位描述。"""
    source = Path(path)
    records: list[JobDescriptionRecord] = []
    seen: set[str] = set()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for source_row_index, row in enumerate(reader):
            title, description, education = parse_job_markup(row.get("user"))
            if not title or not minimum_characters <= len(description) <= maximum_characters:
                continue
            fingerprint = SPACE_RE.sub("", f"{title}\n{description}").casefold()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            records.append(
                JobDescriptionRecord(
                    source_row_index=source_row_index,
                    source_job_id=str(row.get("job_id", "")).strip(),
                    title=title,
                    description=description,
                    education=education,
                )
            )
    return tuple(records)


def choose_evenly_spaced(items: Iterable[JobDescriptionRecord], count: int) -> tuple[JobDescriptionRecord, ...]:
    """从已随机排序的候选中取固定数量，保留岗位标题多样性。"""
    if count <= 0:
        raise ValueError("count 必须大于 0。")
    chosen: list[JobDescriptionRecord] = []
    title_counts: dict[str, int] = {}
    deferred: list[JobDescriptionRecord] = []
    for item in items:
        key = item.title.casefold()
        if title_counts.get(key, 0) >= 2:
            deferred.append(item)
            continue
        chosen.append(item)
        title_counts[key] = title_counts.get(key, 0) + 1
        if len(chosen) == count:
            return tuple(chosen)
    for item in deferred:
        chosen.append(item)
        if len(chosen) == count:
            return tuple(chosen)
    raise ValueError(f"合格且去重后的 JD 不足 {count} 条。")
