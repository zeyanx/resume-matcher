"""加载经过人工发布的建议排序策略；异常时安全回退到原始规则顺序。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config" / "suggestion_policy.json"


@dataclass(frozen=True, slots=True)
class SuggestionPolicy:
    version: str
    status: str
    source: str
    learned_from: int
    minimum_approved_records: int
    kind_weights: dict[str, float]


def load_suggestion_policy(path: Path = DEFAULT_POLICY_PATH) -> SuggestionPolicy:
    """读取策略；只有状态为 approved 的学习策略才会影响建议排序。"""
    baseline = SuggestionPolicy(
        version="baseline-v1",
        status="baseline_not_learned",
        source="规则基线；尚无已发布的满意度学习策略",
        learned_from=0,
        minimum_approved_records=30,
        kind_weights={},
    )
    if not path.is_file():
        return baseline
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        weights = {
            str(name): float(value)
            for name, value in dict(payload.get("kind_weights", {})).items()
            if math.isfinite(float(value)) and 0.5 <= float(value) <= 1.5
        }
        policy = SuggestionPolicy(
            version=str(payload.get("version", baseline.version)),
            status=str(payload.get("status", baseline.status)),
            source=str(payload.get("source", baseline.source)),
            learned_from=max(0, int(payload.get("learned_from", 0))),
            minimum_approved_records=max(3, int(payload.get("minimum_approved_records", 30))),
            kind_weights=weights,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return baseline
    if policy.status != "approved":
        return SuggestionPolicy(
            version=policy.version,
            status=policy.status,
            source=policy.source,
            learned_from=policy.learned_from,
            minimum_approved_records=policy.minimum_approved_records,
            kind_weights={},
        )
    return policy
