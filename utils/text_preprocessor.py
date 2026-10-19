"""中文文本规范化与分词工具。"""

import re
from functools import lru_cache
from pathlib import Path

import jieba


_WHITESPACE_PATTERN = re.compile(r"\s+")
_USEFUL_TOKEN_PATTERN = re.compile(r"[\u4e00-\u9fff]|[a-z0-9+#.]", re.IGNORECASE)
_JIEBA_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "jieba"
_JIEBA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
jieba.dt.tmp_dir = str(_JIEBA_CACHE_DIR)


def normalize_text(text: str | None) -> str:
    """统一大小写和空白，保留中文、英文技能名及必要符号。"""
    if text is None:
        return ""
    return _WHITESPACE_PATTERN.sub(" ", str(text).strip().lower())


@lru_cache(maxsize=512)
def tokenize_chinese(text: str) -> list[str]:
    """使用 jieba 分词，并过滤纯标点和空白词项。"""
    normalized = normalize_text(text)
    if not normalized:
        return []

    return [
        token.strip()
        for token in jieba.lcut(normalized, cut_all=False)
        if token.strip() and _USEFUL_TOKEN_PATTERN.search(token)
    ]
