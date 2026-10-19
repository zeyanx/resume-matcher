"""BGE 语义匹配逻辑测试，不依赖网络或真实模型下载。"""

from pathlib import Path

import numpy as np
import pytest

from models.bge_matcher import (
    BGEModelError,
    calculate_bge_similarity,
    is_offline_mode,
    resolve_model_source,
    split_text_for_embedding,
)


class FakeSemanticModel:
    """根据关键词返回确定向量，验证文档聚合和余弦计算。"""

    def encode(self, chunks: list[str], **_: object) -> np.ndarray:
        vectors = []
        for chunk in chunks:
            if any(word in chunk for word in ("python", "flask", "sql", "后端")):
                vectors.append([1.0, 0.0, 0.0])
            elif any(word in chunk for word in ("海报", "插画", "设计")):
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return np.asarray(vectors, dtype=np.float32)


class ZeroVectorModel:
    """返回零向量，用于验证异常防护。"""

    def encode(self, chunks: list[str], **_: object) -> np.ndarray:
        return np.zeros((len(chunks), 3), dtype=np.float32)


def test_related_semantic_text_scores_higher() -> None:
    model = FakeSemanticModel()
    resume = "熟悉 Python Flask SQL 后端开发"
    related = calculate_bge_similarity(resume, "Python 后端岗位要求 Flask", model)
    unrelated = calculate_bge_similarity(resume, "负责品牌海报和插画设计", model)
    assert related.score == pytest.approx(1.0)
    assert unrelated.score == pytest.approx(0.0)


def test_semantic_result_contains_chunk_counts() -> None:
    result = calculate_bge_similarity("Python\nFlask", "Python", FakeSemanticModel())
    assert result.resume_chunks == 1
    assert result.jd_chunks == 1
    assert -1.0 <= result.raw_cosine <= 1.0


def test_split_long_text_without_losing_limit() -> None:
    chunks = split_text_for_embedding("a" * 25, max_characters=10, max_chunks=4)
    assert [len(chunk) for chunk in chunks] == [10, 10, 5]


def test_split_respects_max_chunks() -> None:
    chunks = split_text_for_embedding("a" * 100, max_characters=10, max_chunks=3)
    assert len(chunks) == 3


@pytest.mark.parametrize("text", ["", " \n "])
def test_reject_empty_semantic_input(text: str) -> None:
    with pytest.raises(ValueError, match="简历内容为空"):
        calculate_bge_similarity(text, "有效岗位", FakeSemanticModel())


def test_reject_zero_embedding() -> None:
    with pytest.raises(BGEModelError, match="零向量"):
        calculate_bge_similarity("Python", "Python", ZeroVectorModel())


@pytest.mark.parametrize("value", ["1", "true", "YES", "on"])
def test_offline_true_values(value: str) -> None:
    assert is_offline_mode(value)


def test_resolve_existing_local_model_path(tmp_path: Path) -> None:
    assert resolve_model_source(str(tmp_path)) == str(tmp_path.resolve())


def test_reject_missing_local_model_path(tmp_path: Path) -> None:
    with pytest.raises(BGEModelError, match="目录不存在"):
        resolve_model_source(str(tmp_path / "missing"))
