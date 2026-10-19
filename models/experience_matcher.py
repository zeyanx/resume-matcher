"""基于可解释词典的经历或职责关键词覆盖分析。"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KEYWORD_PATH = PROJECT_ROOT / "data" / "experience_keywords.json"
ASCII_WORD = re.compile(r"[a-z0-9]", re.IGNORECASE)


class ExperienceCatalogError(ValueError):
    """经历关键词词典无效时抛出的异常。"""


@dataclass(frozen=True, slots=True)
class ExperienceKeyword:
    """一项标准经历关键词。"""

    canonical: str
    category: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExperienceExtraction:
    """文本中识别出的经历关键词与证据。"""

    keywords: tuple[str, ...]
    evidence: dict[str, tuple[str, ...]]
    categories: dict[str, str]


@dataclass(frozen=True, slots=True)
class ExperienceMatchResult:
    """简历相对于 JD 的经历关键词覆盖结果。"""

    score: float
    is_available: bool
    resume: ExperienceExtraction
    jd: ExperienceExtraction
    matched_keywords: tuple[str, ...]
    missing_keywords: tuple[str, ...]
    years_status: str = "未识别（采用经历关键词覆盖，不推断工作年限）"


def _normalize(text: str | None) -> str:
    """统一字符宽度、大小写和空白。"""
    if text is None:
        return ""
    value = unicodedata.normalize("NFKC", str(text)).lower()
    return re.sub(r"\s+", " ", value).strip()


@lru_cache(maxsize=8)
def load_experience_catalog(
    path: str | Path = DEFAULT_KEYWORD_PATH,
) -> tuple[ExperienceKeyword, ...]:
    """读取并验证经历关键词词典。"""
    catalog_path = Path(path)
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperienceCatalogError(f"经历关键词词典无法读取：{catalog_path}") from exc

    raw_items = payload.get("keywords")
    if not isinstance(raw_items, list) or not raw_items:
        raise ExperienceCatalogError("经历关键词词典必须包含非空的 keywords 列表。")

    definitions: list[ExperienceKeyword] = []
    canonical_names: set[str] = set()
    alias_owners: dict[str, str] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ExperienceCatalogError("经历关键词词典中的每项必须是对象。")
        canonical = str(item.get("canonical", "")).strip()
        category = str(item.get("category", "")).strip()
        raw_aliases = item.get("aliases", [])
        if not canonical or not category or not isinstance(raw_aliases, list):
            raise ExperienceCatalogError("每项经历关键词必须包含 canonical、category 和 aliases。")
        if canonical in canonical_names:
            raise ExperienceCatalogError(f"经历关键词名称重复：{canonical}")
        canonical_names.add(canonical)

        aliases = {_normalize(canonical)}
        aliases.update(_normalize(alias) for alias in raw_aliases if str(alias).strip())
        aliases.discard("")
        for alias in aliases:
            owner = alias_owners.get(alias)
            if owner and owner != canonical:
                raise ExperienceCatalogError(
                    f"经历关键词别名冲突：{alias} 同时属于 {owner} 和 {canonical}"
                )
            alias_owners[alias] = canonical
        definitions.append(
            ExperienceKeyword(
                canonical=canonical,
                category=category,
                aliases=tuple(sorted(aliases, key=lambda value: (-len(value), value))),
            )
        )
    return tuple(definitions)


@lru_cache(maxsize=512)
def _alias_pattern(alias: str) -> re.Pattern[str]:
    """建立中英文兼容且保护英文短词边界的表达式。"""
    escaped = re.escape(alias).replace(r"\ ", r"\s+")
    prefix = r"(?<![a-z0-9])" if alias and ASCII_WORD.match(alias[0]) else ""
    suffix = r"(?![a-z0-9])" if alias and ASCII_WORD.match(alias[-1]) else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


def extract_experience_keywords(
    text: str | None,
    catalog: tuple[ExperienceKeyword, ...] | None = None,
) -> ExperienceExtraction:
    """从文本中提取经历、职责和教育要求关键词。"""
    normalized = _normalize(text)
    definitions = catalog or load_experience_catalog()
    evidence: dict[str, tuple[str, ...]] = {}
    categories: dict[str, str] = {}
    if normalized:
        for definition in definitions:
            aliases = tuple(
                alias for alias in definition.aliases if _alias_pattern(alias).search(normalized)
            )
            if aliases:
                evidence[definition.canonical] = aliases
                categories[definition.canonical] = definition.category
    keywords = tuple(sorted(evidence, key=str.casefold))
    return ExperienceExtraction(keywords=keywords, evidence=evidence, categories=categories)


def calculate_experience_match(
    resume_text: str | None,
    jd_text: str | None,
    catalog: tuple[ExperienceKeyword, ...] | None = None,
) -> ExperienceMatchResult:
    """计算 JD 经历关键词在简历中的覆盖率，固定返回 0 到 1。"""
    definitions = catalog or load_experience_catalog()
    resume = extract_experience_keywords(resume_text, definitions)
    jd = extract_experience_keywords(jd_text, definitions)
    resume_set = set(resume.keywords)
    jd_set = set(jd.keywords)
    matched = tuple(sorted(resume_set & jd_set, key=str.casefold))
    missing = tuple(sorted(jd_set - resume_set, key=str.casefold))
    available = bool(jd_set)
    score = len(matched) / len(jd_set) if available else 0.0
    return ExperienceMatchResult(
        score=score,
        is_available=available,
        resume=resume,
        jd=jd,
        matched_keywords=matched,
        missing_keywords=missing,
    )
