"""中文文本预处理测试。"""

from utils.text_preprocessor import normalize_text, tokenize_chinese


def test_normalize_text() -> None:
    assert normalize_text("  Python\n  SQL  ") == "python sql"


def test_tokenize_keeps_chinese_and_technical_terms() -> None:
    tokens = tokenize_chinese("熟悉 Python、SQL 和机器学习")
    assert "python" in tokens
    assert "sql" in tokens
    assert any("机器" in token or "学习" in token for token in tokens)


def test_tokenize_empty_text() -> None:
    assert tokenize_chinese(" \n ") == []
