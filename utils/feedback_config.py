"""反馈收集配置：缺少明确配置时保持关闭。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


TRUE_VALUES = {"1", "true", "yes", "on"}


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUE_VALUES


def _get_value(secrets: Mapping[str, Any] | None, name: str, default: object = "") -> object:
    environment_value = os.getenv(name)
    if environment_value is not None:
        return environment_value
    if secrets is not None:
        try:
            return secrets.get(name, default)
        except (AttributeError, KeyError, TypeError):
            pass
    return default


@dataclass(frozen=True, slots=True)
class FeedbackSettings:
    """公开反馈功能的最小配置。"""

    enabled: bool
    database_url: str
    privacy_contact: str
    retention_days: int
    allow_research_text: bool
    consent_version: str
    disabled_reason: str = ""


def load_feedback_settings(secrets: Mapping[str, Any] | None = None) -> FeedbackSettings:
    """从环境变量或 Streamlit secrets 读取配置，不泄露密钥内容。"""
    requested = _as_bool(_get_value(secrets, "ENABLE_FEEDBACK_COLLECTION", False))
    database_url = str(_get_value(secrets, "FEEDBACK_DATABASE_URL", "")).strip()
    privacy_contact = str(_get_value(secrets, "PRIVACY_CONTACT", "")).strip()
    allow_research_text = _as_bool(_get_value(secrets, "ALLOW_RESEARCH_TEXT", False))
    consent_version = str(_get_value(secrets, "CONSENT_VERSION", "2026-10-19-v1")).strip()
    try:
        retention_days = int(_get_value(secrets, "DATA_RETENTION_DAYS", 180))
    except (TypeError, ValueError):
        retention_days = 180
    retention_days = min(max(retention_days, 1), 3650)

    missing: list[str] = []
    if not requested:
        missing.append("未启用反馈收集")
    if not database_url:
        missing.append("未配置持久化数据库")
    if not privacy_contact:
        missing.append("未配置隐私联系人")
    enabled = not missing
    return FeedbackSettings(
        enabled=enabled,
        database_url=database_url,
        privacy_contact=privacy_contact,
        retention_days=retention_days,
        allow_research_text=allow_research_text,
        consent_version=consent_version or "2026-10-19-v1",
        disabled_reason="；".join(missing),
    )
