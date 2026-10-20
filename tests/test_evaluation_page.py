"""评估实验页面冒烟测试。"""

from pathlib import Path

from streamlit.testing.v1 import AppTest


PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "4_评估实验.py"


def test_evaluation_page_runs_without_exception() -> None:
    page = AppTest.from_file(str(PAGE_PATH), default_timeout=15).run()
    assert not page.exception
    assert page.title[0].value == "人工标注评估实验"
    assert page.metric[0].value == "300/300"
    assert any("全部 300 对" in success.value for success in page.success)
