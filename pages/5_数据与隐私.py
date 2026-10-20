"""公开部署的数据说明与自助删除入口。"""

import streamlit as st

from utils.feedback_config import load_feedback_settings
from utils.feedback_store import FeedbackStore, FeedbackStoreError


def get_settings():
    try:
        return load_feedback_settings(st.secrets)
    except (FileNotFoundError, RuntimeError):
        return load_feedback_settings()


def main() -> None:
    st.set_page_config(page_title="数据与隐私", page_icon="🔐", layout="centered")
    settings = get_settings()

    st.title("数据与隐私")
    st.markdown(
        """
        **匹配不等于收集。** 你可以直接使用简历匹配功能而不提交任何反馈。

        只有在主页面或“简历优化建议”页主动点击提交并勾选同意后，系统才会保存：人工相关性标签、
        帮助程度，或建议满意度、所选有用建议类别及派生特征，以及经过常见个人信息过滤的补充意见。
        默认不保存简历和 JD 正文。

        如果部署者开启了研究文本选项，你还需要第二次单独勾选，系统才会保存经过自动脱敏的
        简历和 JD 文本。自动脱敏不能保证识别全部个人信息，因此请先自行删除敏感内容。

        所有新反馈先进入“待审核”状态。系统不会根据单条输入在线自动更新模型；只有人工审核通过、
        数据量达到最低要求并保留独立测试集后，才能离线生成候选权重或建议排序策略，候选结果也不会自动发布。
        """
    )

    st.subheader("保留与联系")
    st.write(f"配置的数据最长保留期：{settings.retention_days} 天。")
    if settings.privacy_contact:
        st.write(f"隐私与数据请求联系人：{settings.privacy_contact}")
    else:
        st.warning("当前部署未配置隐私联系人，因此反馈收集功能保持关闭。")

    st.subheader("使用删除码删除反馈")
    if not settings.enabled:
        st.info("当前部署未启用反馈收集，没有可通过此页面新增的数据。")
        return

    with st.form("delete_feedback_form"):
        deletion_token = st.text_input("删除码", type="password")
        confirmed = st.checkbox("我确认永久删除与此删除码对应的反馈记录。")
        submitted = st.form_submit_button("永久删除反馈", use_container_width=True)
    if submitted:
        if not confirmed:
            st.warning("请先确认删除。")
            return
        try:
            store = FeedbackStore(settings.database_url, settings.retention_days)
            store.initialize()
            deleted = store.delete_by_token(deletion_token)
        except FeedbackStoreError as exc:
            st.error(str(exc))
        else:
            if deleted:
                st.success("反馈记录已永久删除。")
            else:
                st.warning("未找到对应记录。请检查删除码是否完整。")


if __name__ == "__main__":
    main()
