"""基于可扩展词典、正则边界和同义词归一化的技能提取。"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_PATH = PROJECT_ROOT / "data" / "skills.json"
ASCII_WORD = re.compile(r"[a-z0-9]", re.IGNORECASE)


class SkillCatalogError(ValueError):
    """技能词典结构无效时抛出的异常。"""


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    """一项标准技能及其可识别别名。"""

    canonical: str
    category: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SkillExtraction:
    """一段文本中的标准技能和实际命中别名。"""

    skills: tuple[str, ...]
    evidence: dict[str, tuple[str, ...]]
    categories: dict[str, str]


@dataclass(frozen=True, slots=True)
class SkillGapAnalysis:
    """简历与 JD 的技能差距结果。"""

    resume: SkillExtraction
    jd: SkillExtraction
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]
    extra_skills: tuple[str, ...]
    coverage_rate: float


def normalize_skill_text(text: str | None) -> str:
    """统一全角字符、大小写与空白，保留技能符号。"""
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text)).lower()
    return re.sub(r"\s+", " ", normalized).strip()


@lru_cache(maxsize=8)
def load_skill_catalog(path: str | Path = DEFAULT_SKILL_PATH) -> tuple[SkillDefinition, ...]:
    """读取并验证技能词典；结果按路径缓存。"""
    catalog_path = Path(path)
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillCatalogError(f"技能词典无法读取：{catalog_path}") from exc

    raw_skills = payload.get("skills")
    if not isinstance(raw_skills, list) or not raw_skills:
        raise SkillCatalogError("技能词典必须包含非空的 skills 列表。")

    definitions: list[SkillDefinition] = []
    canonical_names: set[str] = set()
    alias_owners: dict[str, str] = {}
    for item in raw_skills:
        if not isinstance(item, dict):
            raise SkillCatalogError("技能词典中的每个技能必须是对象。")
        canonical = str(item.get("canonical", "")).strip()
        category = str(item.get("category", "")).strip()
        raw_aliases = item.get("aliases", [])
        if not canonical or not category or not isinstance(raw_aliases, list):
            raise SkillCatalogError("每项技能必须包含 canonical、category 和 aliases。")
        if canonical in canonical_names:
            raise SkillCatalogError(f"技能名称重复：{canonical}")
        canonical_names.add(canonical)

        aliases = {normalize_skill_text(canonical)}
        aliases.update(normalize_skill_text(alias) for alias in raw_aliases if str(alias).strip())
        aliases.discard("")
        for alias in aliases:
            owner = alias_owners.get(alias)
            if owner and owner != canonical:
                raise SkillCatalogError(f"技能别名冲突：{alias} 同时属于 {owner} 和 {canonical}")
            alias_owners[alias] = canonical

        definitions.append(
            SkillDefinition(
                canonical=canonical,
                category=category,
                aliases=tuple(sorted(aliases, key=lambda value: (-len(value), value))),
            )
        )

    return tuple(definitions)


@lru_cache(maxsize=512)
def _alias_pattern(alias: str) -> re.Pattern[str]:
    """为中英文技能别名建立边界安全的正则表达式。"""
    escaped = re.escape(alias).replace(r"\ ", r"\s+")
    prefix = r"(?<![a-z0-9])" if alias and ASCII_WORD.match(alias[0]) else ""
    suffix = r"(?![a-z0-9])" if alias and ASCII_WORD.match(alias[-1]) else ""
    return re.compile(prefix + escaped + suffix, re.IGNORECASE)


def extract_skills(
    text: str | None,
    catalog: tuple[SkillDefinition, ...] | None = None,
) -> SkillExtraction:
    """提取技能并将所有同义词归一为 canonical 名称。"""
    normalized = normalize_skill_text(text)
    definitions = catalog or load_skill_catalog()
    evidence: dict[str, tuple[str, ...]] = {}
    categories: dict[str, str] = {}

    if normalized:
        for definition in definitions:
            matched_aliases = tuple(
                alias for alias in definition.aliases if _alias_pattern(alias).search(normalized)
            )
            if matched_aliases:
                evidence[definition.canonical] = matched_aliases
                categories[definition.canonical] = definition.category

    ordered_skills = tuple(sorted(evidence, key=str.casefold))
    return SkillExtraction(skills=ordered_skills, evidence=evidence, categories=categories)


def analyze_skill_gap(
    resume_text: str | None,
    jd_text: str | None,
    catalog: tuple[SkillDefinition, ...] | None = None,
) -> SkillGapAnalysis:
    """计算已匹配、缺失、额外技能和岗位技能覆盖率。"""
    definitions = catalog or load_skill_catalog()
    resume = extract_skills(resume_text, definitions)
    jd = extract_skills(jd_text, definitions)

    resume_set = set(resume.skills)
    jd_set = set(jd.skills)
    matched = tuple(sorted(resume_set & jd_set, key=str.casefold))
    missing = tuple(sorted(jd_set - resume_set, key=str.casefold))
    extra = tuple(sorted(resume_set - jd_set, key=str.casefold))
    coverage = len(matched) / len(jd_set) if jd_set else 0.0

    return SkillGapAnalysis(
        resume=resume,
        jd=jd,
        matched_skills=matched,
        missing_skills=missing,
        extra_skills=extra,
        coverage_rate=coverage,
    )
