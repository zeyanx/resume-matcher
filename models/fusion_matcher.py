"""语义、技能和经历子分数的可解释加权融合。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "fusion_weights.json"


class FusionConfigError(ValueError):
    """融合权重无效或配置文件不可读。"""


@dataclass(frozen=True, slots=True)
class FusionWeights:
    """三个归一化子分数的权重。"""

    semantic: float = 0.5
    skill: float = 0.3
    experience: float = 0.2

    def __post_init__(self) -> None:
        values = (self.semantic, self.skill, self.experience)
        if any(not math.isfinite(value) or value < 0 or value > 1 for value in values):
            raise FusionConfigError("融合权重必须是 0 到 1 之间的有限数值。")
        if not math.isclose(sum(values), 1.0, abs_tol=1e-9):
            raise FusionConfigError("语义、技能和经历权重之和必须等于 1。")


@dataclass(frozen=True, slots=True)
class FusionWeightConfig:
    """权重及其可追溯来源。"""

    weights: FusionWeights
    source: str
    validated: bool
    version: str
    note: str


@dataclass(frozen=True, slots=True)
class FusionResult:
    """融合分和参与计算的归一化子分数。"""

    score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    weights: FusionWeights


def normalize_component_score(value: float, name: str) -> float:
    """验证子分数已归一化到 0 到 1，不静默吞掉数据错误。"""
    score = float(value)
    if not math.isfinite(score) or score < 0 or score > 1:
        raise ValueError(f"{name}必须是 0 到 1 之间的有限数值。")
    return score


def calculate_fusion_score(
    semantic_score: float,
    skill_score: float,
    experience_score: float,
    weights: FusionWeights | None = None,
) -> FusionResult:
    """按照 S=α×语义+β×技能+γ×经历计算综合分。"""
    selected = weights or FusionWeights()
    semantic = normalize_component_score(semantic_score, "语义分数")
    skill = normalize_component_score(skill_score, "技能分数")
    experience = normalize_component_score(experience_score, "经历分数")
    score = (
        selected.semantic * semantic
        + selected.skill * skill
        + selected.experience * experience
    )
    return FusionResult(
        score=max(0.0, min(1.0, score)),
        semantic_score=semantic,
        skill_score=skill,
        experience_score=experience,
        weights=selected,
    )


def load_fusion_weight_config(
    path: str | Path = DEFAULT_CONFIG_PATH,
) -> FusionWeightConfig:
    """读取带来源和验证状态的融合权重配置。"""
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        raw_weights = payload["weights"]
        weights = FusionWeights(
            semantic=float(raw_weights["semantic"]),
            skill=float(raw_weights["skill"]),
            experience=float(raw_weights["experience"]),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise FusionConfigError(f"融合权重配置无法读取或格式错误：{config_path}") from exc
    return FusionWeightConfig(
        weights=weights,
        source=str(payload.get("source", "未注明")),
        validated=bool(payload.get("validated", False)),
        version=str(payload.get("version", "未注明")),
        note=str(payload.get("note", "")),
    )
