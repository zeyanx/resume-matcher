"""技能差距分析页面的交互冒烟测试。"""

from pathlib import Path

from streamlit.testing.v1 import AppTest


PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "2_技能差距分析.py"


def test_skill_gap_page_flow() -> None:
    page = AppTest.from_file(str(PAGE_PATH), default_timeout=15).run()
    assert not page.exception

    next(area for area in page.text_area if area.label == "简历文本").set_value(
        "Python Flask MySQL Git"
    ).run()
    next(area for area in page.text_area if area.label == "岗位 JD").set_value(
        "要求 Python、Django、MySQL 和 Docker"
    ).run()
    next(button for button in page.button if button.label == "分析技能差距").click().run()

    assert not page.exception
    assert page.metric[0].label == "岗位技能覆盖率"
    assert page.metric[0].value == "50.00%"
    assert page.metric[3].value == "2"
