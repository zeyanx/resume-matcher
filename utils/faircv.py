"""FairCV 公共数据集的受控读取与敏感字段隔离。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from utils.feedback_store import redact_personal_data


DATASET_ID = "OhMyKing/FairCV"
DATASET_PAGE = "https://huggingface.co/datasets/OhMyKing/FairCV"
ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"
CONFIG = "default"
SPLIT = "train"
MAX_PAGE_LENGTH = 100
PROTECTED_FIELDS = (
    "age",
    "disability",
    "gender",
    "hukou",
    "marriage",
    "political",
)
ALLOWED_CONTEXT_FIELDS = (
    "company_size",
    "industry",
    "position",
    "recruitment_type",
    "skill_level",
)

PERSONAL_SECTION_RE = re.compile(
    r"(?:^|\n)###\s*个人信息\s*.*?(?=\n---\s*(?:\n|$)|\n###\s+|\Z)",
    re.DOTALL,
)
PROTECTED_LINE_RE = re.compile(
    r"^\s*[-*]?\s*\*{0,2}(?:姓名|年龄|性别|婚姻状况|户口地|身体状况|政治面貌|邮箱|电话)"
    r"\*{0,2}\s*[：:].*$",
    re.MULTILINE,
)


class FairCVError(RuntimeError):
    """FairCV 读取或格式验证失败。"""


@dataclass(frozen=True, slots=True)
class FairCVRecord:
    row_index: int
    matching_text: str
    protected_attributes: Mapping[str, str | None]
    context_attributes: Mapping[str, str | None]


@dataclass(frozen=True, slots=True)
class FairCVBatch:
    records: tuple[FairCVRecord, ...]
    total_rows: int
    offset: int
    partial: bool


def remove_protected_content(content: str) -> str:
    """从进入匹配器的文本中移除个人信息区和常见身份字段。"""
    cleaned = PERSONAL_SECTION_RE.sub("\n### 个人信息\n[已从匹配输入中移除]\n", str(content))
    cleaned = PROTECTED_LINE_RE.sub("", cleaned)
    cleaned = redact_personal_data(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def parse_faircv_payload(payload: Mapping[str, Any], offset: int = 0) -> FairCVBatch:
    """验证 Hugging Face rows API 响应并构造隔离后的记录。"""
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise FairCVError("FairCV API 响应缺少 rows 列表。")
    records: list[FairCVRecord] = []
    for item in raw_rows:
        if not isinstance(item, Mapping) or not isinstance(item.get("row"), Mapping):
            raise FairCVError("FairCV API 返回了无法识别的记录。")
        row = item["row"]
        metadata = row.get("metadata")
        content = row.get("content")
        if not isinstance(metadata, Mapping) or not isinstance(content, str):
            raise FairCVError("FairCV 记录缺少 metadata 或 content。")
        row_index = int(item.get("row_idx", offset + len(records)))
        records.append(
            FairCVRecord(
                row_index=row_index,
                matching_text=remove_protected_content(content),
                protected_attributes={key: metadata.get(key) for key in PROTECTED_FIELDS},
                context_attributes={key: metadata.get(key) for key in ALLOWED_CONTEXT_FIELDS},
            )
        )
    try:
        total_rows = int(payload.get("num_rows_total", len(records)))
    except (TypeError, ValueError) as exc:
        raise FairCVError("FairCV API 返回了无效的总行数。") from exc
    return FairCVBatch(
        records=tuple(records),
        total_rows=total_rows,
        offset=offset,
        partial=bool(payload.get("partial", False)),
    )


def fetch_faircv_rows(
    offset: int = 0,
    length: int = 100,
    timeout_seconds: int = 30,
    opener: Callable[..., Any] = urlopen,
) -> FairCVBatch:
    """通过官方数据集查看 API 获取最多 100 条，不下载完整 6GB 数据。"""
    if offset < 0:
        raise FairCVError("offset 不能为负数。")
    if not 1 <= length <= MAX_PAGE_LENGTH:
        raise FairCVError(f"length 必须在 1 到 {MAX_PAGE_LENGTH} 之间。")
    query = urlencode(
        {
            "dataset": DATASET_ID,
            "config": CONFIG,
            "split": SPLIT,
            "offset": offset,
            "length": length,
        }
    )
    request = Request(
        f"{ROWS_ENDPOINT}?{query}",
        headers={"User-Agent": "ResumeMatcher-FairCV-Academic-Audit/1.0"},
    )
    try:
        with opener(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise FairCVError("无法从 Hugging Face 读取 FairCV 样本。") from exc
    if not isinstance(payload, Mapping):
        raise FairCVError("FairCV API 返回格式无效。")
    return parse_faircv_payload(payload, offset=offset)


def protected_attribute_counts(batch: FairCVBatch) -> dict[str, dict[str, int]]:
    """只输出聚合计数，不展示单条敏感属性组合。"""
    result: dict[str, dict[str, int]] = {}
    for field in PROTECTED_FIELDS:
        counts: dict[str, int] = {}
        for record in batch.records:
            value = str(record.protected_attributes.get(field) or "缺失")
            counts[value] = counts.get(value, 0) + 1
        result[field] = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    return result
