"""BGE 中文语义向量匹配模块。"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from utils.text_preprocessor import normalize_text


DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_PATH_ENV = "RESUME_MATCHER_BGE_PATH"
MODEL_CACHE_ENV = "RESUME_MATCHER_HF_CACHE"
OFFLINE_ENV = "RESUME_MATCHER_OFFLINE"
DEFAULT_CHUNK_CHARACTERS = 800
MAX_CHUNKS = 64


class BGEModelError(RuntimeError):
    """BGE 模型无法加载或推理时抛出的用户可读异常。"""


@dataclass(frozen=True, slots=True)
class SemanticMatchResult:
    """BGE 语义匹配结果。"""

    score: float
    raw_cosine: float
    resume_chunks: int
    jd_chunks: int


def is_offline_mode(value: str | None = None) -> bool:
    """读取布尔环境配置，支持常见的真值写法。"""
    raw_value = value if value is not None else os.getenv(OFFLINE_ENV, "")
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_model_source(local_model_path: str | None = None) -> str:
    """优先使用页面参数或环境变量指定的本地模型目录。"""
    configured_path = (local_model_path or os.getenv(MODEL_PATH_ENV, "")).strip()
    if not configured_path:
        return DEFAULT_MODEL_NAME

    model_path = Path(configured_path).expanduser().resolve()
    if not model_path.is_dir():
        raise BGEModelError(f"本地 BGE 模型目录不存在：{model_path}")
    return str(model_path)


def split_text_for_embedding(
    text: str,
    max_characters: int = DEFAULT_CHUNK_CHARACTERS,
    max_chunks: int = MAX_CHUNKS,
) -> list[str]:
    """按段落和字符上限切分长文本，减少模型截断造成的信息损失。"""
    normalized = normalize_text(text)
    if not normalized:
        return []
    if max_characters <= 0 or max_chunks <= 0:
        raise ValueError("分块参数必须大于 0。")

    paragraphs = [part.strip() for part in re.split(r"\n+", text) if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        paragraph = normalize_text(paragraph)
        while len(paragraph) > max_characters:
            if current:
                chunks.append(current)
                current = ""
                if len(chunks) >= max_chunks:
                    return chunks
            chunks.append(paragraph[:max_characters])
            paragraph = paragraph[max_characters:]
            if len(chunks) >= max_chunks:
                return chunks

        candidate = f"{current} {paragraph}".strip() if current else paragraph
        if len(candidate) <= max_characters:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph
            if len(chunks) >= max_chunks:
                return chunks

    if current and len(chunks) < max_chunks:
        chunks.append(current)
    return chunks


def load_bge_model(
    local_model_path: str | None = None,
    cache_folder: str | None = None,
    offline: bool | None = None,
    device: str | None = None,
) -> Any:
    """加载 BGE 模型；首次在线运行会下载到指定缓存目录。"""
    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise BGEModelError(
            "缺少 sentence-transformers 或 PyTorch，请先安装 requirements.txt。"
        ) from exc

    source = resolve_model_source(local_model_path)
    cache = (cache_folder or os.getenv(MODEL_CACHE_ENV, "")).strip() or None
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
    use_offline = is_offline_mode() if offline is None else offline
    selected_device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    try:
        return SentenceTransformer(
            source,
            cache_folder=cache,
            device=selected_device,
            local_files_only=use_offline,
            trust_remote_code=False,
        )
    except Exception as exc:
        mode_hint = "离线模式下未找到完整模型缓存" if use_offline else "模型下载或加载失败"
        raise BGEModelError(
            f"{mode_hint}。可检查网络，或在页面中指定本地 BGE 模型目录。"
        ) from exc


def _mean_document_embedding(model: Any, chunks: list[str]) -> np.ndarray:
    """对文本块向量取均值后再次归一化，得到文档级向量。"""
    try:
        embeddings = model.encode(
            chunks,
            batch_size=16,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    except Exception as exc:
        raise BGEModelError("BGE 模型推理失败，请检查模型文件和可用内存。") from exc

    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    if matrix.ndim != 2 or matrix.shape[0] != len(chunks):
        raise BGEModelError("BGE 模型返回了无法识别的向量形状。")

    document_vector = matrix.mean(axis=0)
    norm = float(np.linalg.norm(document_vector))
    if not np.isfinite(norm) or norm == 0:
        raise BGEModelError("BGE 模型生成了无效的零向量。")
    return document_vector / norm


def calculate_bge_similarity(
    resume_text: str,
    jd_text: str,
    model: Any,
) -> SemanticMatchResult:
    """计算简历和 JD 的 BGE 文档级余弦相似度。"""
    resume_chunks = split_text_for_embedding(resume_text)
    jd_chunks = split_text_for_embedding(jd_text)
    if not resume_chunks:
        raise ValueError("简历内容为空，无法计算 BGE 语义匹配度。")
    if not jd_chunks:
        raise ValueError("岗位 JD 为空，无法计算 BGE 语义匹配度。")

    resume_vector = _mean_document_embedding(model, resume_chunks)
    jd_vector = _mean_document_embedding(model, jd_chunks)
    raw_cosine = float(np.dot(resume_vector, jd_vector))
    if not np.isfinite(raw_cosine):
        raise BGEModelError("BGE 余弦相似度不是有效数值。")

    score = float(np.clip(raw_cosine, 0.0, 1.0))
    return SemanticMatchResult(
        score=score,
        raw_cosine=raw_cosine,
        resume_chunks=len(resume_chunks),
        jd_chunks=len(jd_chunks),
    )
