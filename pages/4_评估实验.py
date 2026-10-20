"""基于当前人工标注进度，实时展示可复现的评估实验结果。"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.evaluate import (  # noqa: E402
    HUMAN_LABEL_STATUSES,
    calculate_metrics,
    load_evaluation_cases,
    prediction_functions,
)
from evaluation.weight_search import LabeledScoreCase, run_weight_grid_search  # noqa: E402


DEFAULT_CASES = PROJECT_ROOT / "data" / "test_cases.csv"
CLASSIFICATION_THRESHOLD = 0.5
WEIGHT_STEP = 0.1


@st.cache_data(show_spinner=False)
def load_annotations(path_text: str, modified_ns: int) -> pd.DataFrame:
    """按文件修改时间缓存标注表，避免页面交互时重复解析。"""
    del modified_ns
    return pd.read_csv(path_text, encoding="utf-8-sig")


@st.cache_data(show_spinner=False)
def calculate_experiment(path_text: str, modified_ns: int) -> dict[str, object]:
    """只筛选真人标签，验证集选权重，测试集只做最终评估。"""
    del modified_ns
    cases = load_evaluation_cases(path_text, human_labeled_only=True)
    score_cases = tuple(
        LabeledScoreCase(
            case_id=case.case_id,
            split=case.split,
            relevance_label=case.relevance_label,
            semantic_score=case.semantic_score,
            skill_score=case.skill_score,
            experience_score=case.experience_score,
            data_status=case.data_status,
        )
        for case in cases
    )
    search = run_weight_grid_search(score_cases, step=WEIGHT_STEP)
    predictors = prediction_functions(search.best_validation.weights)
    metrics = pd.DataFrame(
        [
            asdict(
                calculate_metrics(
                    cases,
                    algorithm,
                    predictor,
                    split="test",
                    classification_threshold=CLASSIFICATION_THRESHOLD,
                )
            )
            for algorithm, predictor in predictors.items()
        ]
    )

    test_categories = sorted({case.job_category for case in cases if case.split == "test"})
    category_metrics = pd.DataFrame(
        [
            asdict(
                calculate_metrics(
                    cases,
                    algorithm,
                    predictor,
                    split="test",
                    category=category,
                    classification_threshold=CLASSIFICATION_THRESHOLD,
                )
            )
            for category in test_categories
            for algorithm, predictor in predictors.items()
        ]
    )

    error_rows: list[dict[str, object]] = []
    for algorithm, predictor in predictors.items():
        for case in cases:
            if case.split != "test":
                continue
            prediction = predictor(case)
            error_rows.append(
                {
                    "algorithm": algorithm,
                    "case_id": case.case_id,
                    "query_id": case.query_id,
                    "job_category": case.job_category,
                    "relevance_label": case.relevance_label,
                    "prediction": prediction,
                    "absolute_error": abs(prediction - case.normalized_label),
                }
            )
    errors = pd.DataFrame(error_rows).sort_values(
        ["absolute_error", "case_id"], ascending=[False, True]
    )
    weight_comparison = pd.DataFrame(
        [
            {
                "rank": rank,
                "semantic_weight": item.weights.semantic,
                "skill_weight": item.weights.skill,
                "experience_weight": item.weights.experience,
                "validation_spearman": item.spearman,
                "validation_mae": item.mae,
                "validation_rmse": item.rmse,
            }
            for rank, item in enumerate(search.comparisons, start=1)
        ]
    )
    test_cases = [case for case in cases if case.split == "test"]
    query_max_label: dict[str, float] = {}
    for case in test_cases:
        query_max_label[case.query_id] = max(
            query_max_label.get(case.query_id, 0.0), case.relevance_label
        )

    return {
        "metrics": metrics,
        "category_metrics": category_metrics,
        "errors": errors,
        "weight_comparison": weight_comparison,
        "weights": asdict(search.best_validation.weights),
        "validation_spearman": search.best_validation.spearman,
        "validation_mae": search.best_validation.mae,
        "validation_count": sum(case.split == "validation" for case in cases),
        "test_count": len(test_cases),
        "test_query_count": len(query_max_label),
        "test_queries_without_relevant": sum(value < 2 for value in query_max_label.values()),
        "job_categories": test_categories,
        "data_statuses": sorted({case.data_status for case in cases}),
    }


def _metric_table(metrics: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "algorithm": "算法",
        "pearson": "Pearson",
        "spearman": "Spearman",
        "ndcg_at_5": "NDCG@5",
        "mrr": "MRR",
        "mae": "MAE",
        "rmse": "RMSE",
    }
    return metrics[list(columns)].rename(columns=columns).round(4)


def main() -> None:
    st.set_page_config(page_title="人工标注评估实验", page_icon="📊", layout="wide")
    st.title("人工标注评估实验")
    st.caption(
        "使用固定 validation/test 切分：融合权重只在验证集选择，测试集仅用于最终一次比较。"
    )

    if not DEFAULT_CASES.exists():
        st.error("未找到人工标注数据文件。")
        return

    modified_ns = DEFAULT_CASES.stat().st_mtime_ns
    try:
        annotations = load_annotations(str(DEFAULT_CASES), modified_ns)
        result = calculate_experiment(str(DEFAULT_CASES), modified_ns)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"评估数据无法使用：{exc}")
        return

    human_mask = annotations["label_status"].isin(HUMAN_LABEL_STATUSES)
    labeled = annotations[human_mask & annotations["relevance_label"].notna()].copy()
    total_count = len(annotations)
    labeled_count = len(labeled)
    pending_count = total_count - labeled_count

    overview = st.columns(5)
    overview[0].metric("已人工标注", f"{labeled_count}/{total_count}")
    overview[1].metric("验证集记录", int(result["validation_count"]))
    overview[2].metric("测试集记录", int(result["test_count"]))
    overview[3].metric("测试查询组", int(result["test_query_count"]))
    overview[4].metric("测试岗位类别", len(result["job_categories"]))
    st.progress(labeled_count / total_count, text=f"标注进度 {labeled_count}/{total_count}")

    st.warning(
        "当前是阶段性结果：简历来自 FairCV 合成数据，JD 来自公开数据，标签由人工给出。"
        "结果只适用于该固定基准，不能解释为真实招聘准确率或录用概率。"
    )
    if pending_count:
        st.info(f"仍有 {pending_count} 对待标注；本页自动忽略这些记录，只计算已完成人工标注的子集。")

    label_counts = (
        labeled.assign(relevance_label=labeled["relevance_label"].astype(int))
        .groupby(["split", "relevance_label"], as_index=False)
        .size()
        .rename(columns={"size": "数量", "split": "数据切分", "relevance_label": "人工标签"})
    )
    if 3 not in set(label_counts["人工标签"]):
        st.warning("当前 80 条标注中没有“3=高度匹配”样本，标签分布明显不均衡，指标需谨慎解释。")

    st.subheader("人工标签分布")
    label_figure = px.bar(
        label_counts,
        x="人工标签",
        y="数量",
        color="数据切分",
        barmode="group",
        category_orders={"人工标签": [0, 1, 2, 3]},
        text_auto=True,
    )
    label_figure.update_layout(xaxis=dict(dtick=1))
    st.plotly_chart(label_figure, use_container_width=True)

    st.subheader("验证集选择的融合权重")
    weights = result["weights"]
    weight_columns = st.columns(3)
    weight_columns[0].metric("BGE 语义权重", f"{weights['semantic']:.1f}")
    weight_columns[1].metric("技能覆盖权重", f"{weights['skill']:.1f}")
    weight_columns[2].metric("经历匹配权重", f"{weights['experience']:.1f}")
    validation_spearman = result["validation_spearman"]
    correlation_text = "不可计算" if validation_spearman is None else f"{validation_spearman:.4f}"
    st.caption(
        f"网格步长 {WEIGHT_STEP:.1f}；验证集 Spearman={correlation_text}，"
        f"MAE={result['validation_mae']:.4f}。测试集没有参与权重选择。"
    )
    with st.expander("查看验证集前 10 组权重"):
        st.dataframe(
            result["weight_comparison"].head(10).round(4),
            use_container_width=True,
            hide_index=True,
        )

    metrics: pd.DataFrame = result["metrics"]
    st.subheader("测试集排序与误差指标")
    st.dataframe(_metric_table(metrics), use_container_width=True, hide_index=True)
    ranking_long = metrics.melt(
        id_vars=["algorithm"],
        value_vars=["pearson", "spearman", "ndcg_at_5", "mrr"],
        var_name="指标",
        value_name="值",
    )
    ranking_figure = px.bar(
        ranking_long,
        x="algorithm",
        y="值",
        color="指标",
        barmode="group",
        range_y=[-1.0, 1.05],
        labels={"algorithm": "算法"},
    )
    ranking_figure.update_yaxes(zeroline=True, zerolinewidth=1, zerolinecolor="#666")
    st.plotly_chart(ranking_figure, use_container_width=True)
    st.caption(
        "测试集仅 20 对、4 个查询组；其中 "
        f"{result['test_queries_without_relevant']} 个查询组没有标签≥2的候选，"
        "因此 NDCG@5、MRR 和相关系数只能作为当前阶段的初步结果。"
    )

    st.subheader("阈值分类指标")
    classification = metrics[
        ["algorithm", "accuracy", "precision", "recall", "f1", "mae", "rmse"]
    ].rename(
        columns={
            "algorithm": "算法",
            "accuracy": "Accuracy",
            "precision": "Precision",
            "recall": "Recall",
            "f1": "F1",
            "mae": "MAE",
            "rmse": "RMSE",
        }
    )
    st.dataframe(classification.round(4), use_container_width=True, hide_index=True)
    st.caption(
        "正类定义为人工标签≥2，预测阈值为 0.5。测试集正类只有 2 条，"
        "Accuracy 可能被类别不平衡放大，应同时查看 Precision、Recall 和 F1。"
    )

    category_metrics: pd.DataFrame = result["category_metrics"]
    st.subheader("分岗位类别结果")
    selected_algorithm = st.selectbox("选择算法", list(category_metrics["algorithm"].unique()))
    selected = category_metrics[category_metrics["algorithm"] == selected_algorithm]
    st.dataframe(_metric_table(selected), use_container_width=True, hide_index=True)

    st.subheader("误差最大的测试案例")
    st.caption("只展示案例编号、岗位类别和误差，不展示完整简历或 JD 正文。")
    errors: pd.DataFrame = result["errors"]
    context_columns = labeled[["case_id", "resume_position", "jd_title"]].drop_duplicates("case_id")
    errors = errors.merge(context_columns, on="case_id", how="left")
    error_view = errors[
        [
            "algorithm",
            "case_id",
            "resume_position",
            "jd_title",
            "relevance_label",
            "prediction",
            "absolute_error",
        ]
    ].head(20)
    st.dataframe(error_view.round(4), use_container_width=True, hide_index=True)

    st.download_button(
        "下载本次测试集指标 CSV",
        data=metrics.to_csv(index=False).encode("utf-8-sig"),
        file_name="faircv_human_labeled_metrics.csv",
        mime="text/csv",
        use_container_width=True,
    )
    best_spearman = metrics["spearman"].max()
    best_names = "、".join(
        metrics.loc[metrics["spearman"] == best_spearman, "algorithm"].astype(str)
    )
    fusion_mae = float(metrics.loc[metrics["algorithm"] == "融合评分", "mae"].iloc[0])
    st.info(
        f"当前测试集 Spearman 最高的是 {best_names}（{best_spearman:.4f}）；"
        f"融合评分 MAE 为 {fusion_mae:.4f}。这是小样本阶段性结果；"
        "完成剩余标注并增加复核标注者后，应重新运行实验。"
    )


main()
