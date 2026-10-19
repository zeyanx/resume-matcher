"""Public-facing text safety checks kept outside the cached data loader."""

from __future__ import annotations

import re


_SENSITIVE_SECTION_RE = re.compile(
    r"(?:^|\n)---\s*\n+\s*(?:###\s*)?\*{0,2}"
    r"(?:个人信息|参考资料|推荐信息|推荐人|声明|\[?签名\]?)"
    r"\*{0,2}\s*(?:[：:].*)?\n.*?(?=\n---\s*(?:\n|$)|\Z)",
    re.DOTALL,
)
_SENSITIVE_LINE_RE = re.compile(
    r"^\s*[-*]?\s*\*{0,2}(?:姓名|年龄|性别|婚姻状况|户口地|身体状况|政治面貌|邮箱|电话|联系方式|推荐人|声明)"
    r"\*{0,2}\s*[：:].*$",
    re.MULTILINE,
)
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d(?:[- ]?\d){8}(?!\d)")


def sanitize_public_resume(text: str) -> str:
    """Apply a final fail-closed scrub immediately before public display."""
    cleaned = _SENSITIVE_SECTION_RE.sub("\n---\n", str(text))
    cleaned = _SENSITIVE_LINE_RE.sub("", cleaned)
    cleaned = _EMAIL_RE.sub("[邮箱已移除]", cleaned)
    cleaned = _PHONE_RE.sub("[电话已移除]", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned
