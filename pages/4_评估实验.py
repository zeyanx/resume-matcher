"""展示已落盘评估结果及其证据边界。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "stage7_synthetic_demo"


def main() -> None:
    """读取程序生成的 CSV/JSON，而不是在页面里硬编码指标。"""
    st.set_page_config(page_title="评估实验", page_icon="📊", layout="wide")
    st.title("评估实验与可视化")
    st.caption("页面只读取 reports 中的实际运行结果；指标是否有效取决于数据状态和标注质量。")

    summary_path = DEFAULT_REPORT_DIR / "run_summary.json"
    metrics_path = DEFAULT_REPORT_DIR / "metrics.csv"
    category_path = DEFAULT_REPORT_DIR / "category_metrics.csv"
    error_path = DEFAULT_REPORT_DIR / "error_cases.csv"
    config_path = DEFAULT_REPORT_DIR / "best_config.json"
    if not all(path.exists() for path in (summary_path, metrics_path, category_path, error_path, config_path)):
        st.warning(
            "尚未找到阶段 7 评估输出。请先运行 evaluation/evaluate.py；"
            "没有人工标注数据时只能使用明确标记的合成演示数据验证流程。"
        )
        return

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    statuses = summary.get("data_statuses", [])
    if "synthetic_demo" in statuses:
        st.error("当前结果来自 synthetic_demo：尚未形成有效实验结论，不得用于论文性能结论或招聘决策。")
    else:
        st.success("当前结果未标记为合成数据；仍需结合数据卡和标注质量审阅。")

    overview = st.columns(4)
    overview[0].metric("验证集记录", summary.get("validation_count", 0))
    overview[1].metric("测试集记录", summary.get("test_count", 0))
    overview[2].metric("查询组数", summary.get("query_count", 0))
    overview[3].metric("随机种子", config.get("random_seed", "未记录"))
    weights = config.get("weights", {})
    if weights:
        st.caption(
            "权重只在 validation 上选择："
            f"语义 {weights.get('semantic', 0):.2f} / 技能 {weights.get('skill', 0):.2f} / "
            f"经历 {weights.get('experience', 0):.2f}；测试集不参与选择。"
        )
    else:
        st.caption("当前只有合成流程数据，因此没有保存可用于结论的正式最佳权重。")

    metrics = pd.read_csv(metrics_path, encoding="utf-8-sig")
    st.subheader("测试集算法对比")
    if metrics.empty:
        st.info("指标表目前只有字段结构；获得真实人工标注测试集后才会生成数值和图表。")
    else:
        st.dataframe(metrics, use_container_width=True, hide_index=True)
        long_metrics = metrics.melt(
            id_vars=["algorithm"],
            value_vars=["pearson", "spearman", "ndcg_at_5", "mrr"],
            var_name="指标",
            value_name="值",
        )
        figure = px.bar(
            long_metrics,
            x="algorithm",
            y="值",
            color="指标",
            barmode="group",
            range_y=[0, 1.05],
            labels={"algorithm": "算法"},
        )
        st.plotly_chart(figure, use_container_width=True)

    category_metrics = pd.read_csv(category_path, encoding="utf-8-sig")
    st.subheader("分岗位类别结果")
    if category_metrics.empty:
        st.info("尚无可报告的分类别指标。")
    else:
        selected_algorithm = st.selectbox("选择算法", list(category_metrics["algorithm"].unique()))
        selected = category_metrics[category_metrics["algorithm"] == selected_algorithm]
        st.dataframe(selected, use_container_width=True, hide_index=True)

    st.subheader("异常样本与错误案例")
    st.caption("这里只展示案例编号和分数误差，不包含完整简历或 JD 正文。")
    errors = pd.read_csv(error_path, encoding="utf-8-sig")
    if errors.empty:
        st.info("尚无真实测试集错误案例。")
    else:
        st.dataframe(errors, use_container_width=True, hide_index=True)

    st.info(summary.get("conclusion", "未记录实验结论。"))


main()
