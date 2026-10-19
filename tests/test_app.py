"""Streamlit 页面交互冒烟测试。"""

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_example_matching_flow() -> None:
    """合成示例应能完成一次无异常的 TF-IDF 匹配。"""
    app = AppTest.from_file(str(APP_PATH), default_timeout=15).run()
    assert not app.exception

    # 页面交互测试不访问网络；BGE 推理由独立测试和真实运行检查覆盖。
    next(toggle for toggle in app.toggle if toggle.label == "启用 BGE 语义匹配").set_value(
        False
    ).run()

    next(button for button in app.button if button.label == "载入内置离线示例").click().run()
    assert "Python 后端开发实习生" in app.text_area[0].value
    assert "岗位职责" in app.text_area[1].value

    next(button for button in app.button if button.label == "开始匹配").click().run()
    assert not app.exception
    assert app.metric[0].label == "TF-IDF"
    assert app.metric[0].value.endswith("%")
    assert app.metric[2].label == "技能覆盖"
    assert app.metric[3].label == "经历关键词"
    assert app.metric[4].label == "融合评分"
    assert app.metric[4].value == "不可用"
    assert app.session_state["latest_analysis"]["scores"]["semantic"] is None
    assert app.session_state["latest_analysis"]["text_signature"]
