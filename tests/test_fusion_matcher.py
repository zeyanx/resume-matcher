"""融合分数与权重配置测试。"""

import json

import pytest

from models.fusion_matcher import (
    FusionConfigError,
    FusionWeights,
    calculate_fusion_score,
    load_fusion_weight_config,
)


def test_default_fusion_score() -> None:
    result = calculate_fusion_score(0.8, 0.6, 0.4)
    assert result.score == pytest.approx(0.66)
    assert result.weights == FusionWeights(0.5, 0.3, 0.2)


def test_component_scores_must_be_normalized() -> None:
    with pytest.raises(ValueError, match="0 到 1"):
        calculate_fusion_score(1.2, 0.6, 0.4)


def test_weights_must_sum_to_one() -> None:
    with pytest.raises(FusionConfigError, match="等于 1"):
        FusionWeights(0.5, 0.5, 0.5)


def test_default_config_is_explicitly_unvalidated() -> None:
    config = load_fusion_weight_config()
    assert config.weights == FusionWeights(0.5, 0.3, 0.2)
    assert not config.validated
    assert "未经" in config.source


def test_invalid_config_is_rejected(tmp_path) -> None:
    path = tmp_path / "weights.json"
    path.write_text(json.dumps({"weights": {"semantic": 1, "skill": 1}}), encoding="utf-8")
    with pytest.raises(FusionConfigError, match="无法读取"):
        load_fusion_weight_config(path)
