from pathlib import Path

from streamlit.testing.v1 import AppTest


PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "6_基础数据与公平性.py"


def test_faircv_page_renders_without_downloading_data():
    app = AppTest.from_file(str(PAGE_PATH), default_timeout=15).run()
    assert not app.exception
    assert app.title[0].value == "基础数据与公平性"
    assert "模拟生成" in [metric.value for metric in app.metric]
    assert any(button.label == "读取并聚合 FairCV 样本" for button in app.button)
