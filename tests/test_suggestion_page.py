"""简历优化建议页面交互冒烟测试。"""

from pathlib import Path

from streamlit.testing.v1 import AppTest


PAGE_PATH = Path(__file__).resolve().parents[1] / "pages" / "3_简历优化建议.py"


def test_suggestion_page_generates_advice_and_downloads() -> None:
    page = AppTest.from_file(str(PAGE_PATH), default_timeout=15).run()
    assert not page.exception

    next(area for area in page.text_area if area.label == "简历文本").set_value(
        "技能：Python、Flask。项目经历：完成软件开发和测试。"
    ).run()
    next(area for area in page.text_area if area.label == "岗位 JD").set_value(
        "要求 Python、Django、Docker；负责软件开发、测试、部署和文档维护。"
    ).run()
    next(button for button in page.button if button.label == "生成优化建议与报告").click().run()

    assert not page.exception
    markdown_values = [element.value for element in page.markdown]
    assert any("核对并处理岗位缺失技能" in value for value in markdown_values)
    assert len(page.download_button) == 2
    assert any(element.label == "你对本次简历修改建议的满意度" for element in page.slider)
    assert any(button.label == "提交建议反馈" and button.disabled for button in page.button)
