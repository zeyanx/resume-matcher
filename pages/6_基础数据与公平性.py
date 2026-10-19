"""FairCV 基础数据说明与只读聚合审计。"""

import hashlib

import pandas as pd
import streamlit as st

from utils.faircv import (
    DATASET_PAGE,
    FairCVError,
    fetch_faircv_rows,
    protected_attribute_counts,
)


FIELD_LABELS = {
    "age": "年龄",
    "disability": "身体状况/残障",
    "gender": "性别",
    "hukou": "户口地",
    "marriage": "婚姻状况",
    "political": "政治面貌",
}


@st.cache_data(ttl=1800, show_spinner=False)
def load_audit_sample(seed: int, size: int):
    first = fetch_faircv_rows(offset=0, length=1)
    maximum_offset = max(first.total_rows - size, 0)
    digest = hashlib.sha256(str(seed).encode("ascii")).hexdigest()
    offset = int(digest[:12], 16) % (maximum_offset + 1)
    return fetch_faircv_rows(offset=offset, length=size)


def main() -> None:
    st.set_page_config(page_title="基础数据与公平性", page_icon="⚖️", layout="wide")
    st.title("基础数据与公平性")
    st.markdown(
        f"本项目将 [FairCV]({DATASET_PAGE}) 作为**可选的学术公平性审计基础数据**，"
        "而不是线上用户数据或真实录用标签。"
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("数据状态", "模拟生成")
    col2.metric("数据卡报告规模", "约 144 万条")
    col3.metric("数据卡报告体积", "约 6.32 GB")

    st.warning(
        "数据卡声明仅限学术研究并禁止商业用途，且当前缺少标准机器可读许可证。"
        "若项目用途超出课程或学术研究，请先取得数据作者的明确授权。"
    )
    st.info(
        "年龄、性别、户口、婚姻、政治面貌和残障信息只用于聚合公平性审计，"
        "会从送入匹配算法的文本中删除。FairCV 没有真实录用结果或人工相关性标签，"
        "因此不能直接用于学习融合权重。"
    )

    with st.expander("接入方式与证据边界"):
        st.markdown(
            """
            - 完整数据集不进入 GitHub、交付 ZIP 或 Streamlit 容器；
            - 页面每次最多临时读取 100 条，并只展示聚合计数；
            - 不展示单条简历，不保存抽样内容，不与用户反馈合并；
            - 离线脚本生成可复现抽样及来源清单，但输出目录默认被 Git 忽略；
            - 此处只能检查样本构成，不能据此声称模型已经公平。
            """
        )

    st.subheader("公开样本聚合检查")
    left, right = st.columns(2)
    seed = left.number_input("抽样种子", min_value=0, max_value=2_147_483_647, value=42)
    sample_size = right.slider("临时样本数", min_value=10, max_value=100, value=100, step=10)
    if st.button("读取并聚合 FairCV 样本", type="primary", use_container_width=True):
        try:
            with st.spinner("正在读取 Hugging Face 的公开样本……"):
                batch = load_audit_sample(int(seed), int(sample_size))
        except FairCVError as exc:
            st.error(str(exc))
        else:
            st.success(
                f"已临时读取 {len(batch.records)} 条；数据源当前报告总行数 "
                f"{batch.total_rows:,}。页面未保存单条内容。"
            )
            counts = protected_attribute_counts(batch)
            rows = [
                {
                    "审计字段": FIELD_LABELS[field],
                    "类别": category,
                    "样本数": count,
                }
                for field, categories in counts.items()
                for category, count in categories.items()
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption(
                "这些计数只描述本次连续页样本的构成，不代表总体比例，也不是模型公平性结论。"
            )


if __name__ == "__main__":
    main()
