"""对 FairCV 简历—公开 JD 配对进行人工相关性标注。"""

from __future__ import annotations

import csv
import hashlib
import io
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from utils.faircv import FairCVError, fetch_faircv_rows
from utils.public_text import sanitize_public_resume


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = PROJECT_ROOT / "data" / "test_cases.csv"
LABELS = {
    "未标注": "",
    "0 · 不匹配": "0",
    "1 · 部分匹配": "1",
    "2 · 较匹配": "2",
    "3 · 高度匹配": "3",
}
FAIRCV_SANITIZER_VERSION = "2026-10-19-v3"


@st.cache_data(show_spinner=False, ttl=24 * 60 * 60)
def fetch_resume(row_index: int, sanitizer_version: str = FAIRCV_SANITIZER_VERSION) -> str:
    del sanitizer_version  # 仅用于让 Streamlit 在清洗规则升级后失效旧缓存。
    last_error: Exception | None = None
    batch = None
    for attempt in range(3):
        try:
            batch = fetch_faircv_rows(offset=row_index, length=1, timeout_seconds=20)
            break
        except FairCVError as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    if batch is None:
        raise FairCVError("FairCV 简历连续读取失败，请稍后重试。") from last_error
    if not batch.records or batch.records[0].row_index != row_index:
        raise FairCVError("FairCV 未返回预期的简历记录。")
    return sanitize_public_resume(batch.records[0].matching_text)


def load_rows(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    required = {
        "case_id",
        "resume_source_row_index",
        "jd_title",
        "jd_text",
        "relevance_label",
        "label_status",
    }
    missing = required - set(rows[0] if rows else ())
    if not rows or missing:
        raise ValueError(f"标注 CSV 为空或缺少字段：{', '.join(sorted(missing))}")
    return [{key: str(value or "") for key, value in row.items()} for row in rows]


def export_rows(rows: list[dict[str, str]]) -> bytes:
    fields = list(rows[0])
    for optional in ("annotation_confidence", "annotation_notes"):
        if optional not in fields:
            fields.append(optional)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def main() -> None:
    st.set_page_config(page_title="人工标注", page_icon="✍️", layout="wide")
    st.title("简历—JD 人工标注")
    st.caption("0=不匹配，1=部分匹配，2=较匹配，3=高度匹配")
    st.warning(
        "模型分数只用于构造候选池，不能代替标签。只有真人阅读简历与 JD 后保存的记录，"
        "才会标记为 human_labeled；测试集完成前不会生成正式指标或最优权重。"
    )

    uploaded = st.file_uploader("继续标注已有 CSV（可选）", type=["csv"])
    raw = uploaded.getvalue() if uploaded is not None else DEFAULT_CASES.read_bytes()
    signature = hashlib.sha256(raw).hexdigest()
    if st.session_state.get("annotation_source_signature") != signature:
        try:
            st.session_state["annotation_rows"] = load_rows(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            st.error(str(exc))
            st.stop()
        st.session_state["annotation_source_signature"] = signature

    rows: list[dict[str, str]] = st.session_state["annotation_rows"]
    pending = [index for index, row in enumerate(rows) if row.get("label_status") != "human_labeled"]
    completed = len(rows) - len(pending)
    st.progress(completed / len(rows), text=f"已完成人工标注 {completed}/{len(rows)}")

    annotator_id = st.text_input(
        "标注者代号",
        value=st.session_state.get("annotator_id", ""),
        placeholder="例如 A01；不要填写姓名、邮箱或学号",
    ).strip()
    st.session_state["annotator_id"] = annotator_id

    options = pending if pending else list(range(len(rows)))
    selected_index = st.selectbox(
        "选择配对",
        options=options,
        format_func=lambda index: (
            f"{rows[index]['case_id']} · {rows[index].get('resume_position', '未分类')}"
            f" → {rows[index]['jd_title']}"
        ),
    )
    row = rows[int(selected_index)]

    try:
        with st.spinner("正在读取 FairCV 合成简历……"):
            resume_text = fetch_resume(
                int(row["resume_source_row_index"]), FAIRCV_SANITIZER_VERSION
            )
    except (FairCVError, ValueError) as exc:
        st.error(f"无法读取这份 FairCV 简历：{exc}")
        resume_text = ""

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader(f"合成简历 · {row.get('resume_position', '未分类')}")
        st.text_area("简历正文", value=resume_text, height=500, disabled=True)
    with right:
        st.subheader(f"公开 JD · {row['jd_title']}")
        st.text_area("JD 正文", value=row["jd_text"], height=500, disabled=True)

    current_label = row.get("relevance_label", "")
    current_display = next((label for label, value in LABELS.items() if value == current_label), "未标注")
    label = st.radio(
        "人工匹配等级",
        list(LABELS),
        index=list(LABELS).index(current_display),
        horizontal=True,
    )
    confidence = st.select_slider(
        "标注信心",
        options=["低", "中", "高"],
        value=row.get("annotation_confidence") or "中",
    )
    notes = st.text_input(
        "判定备注（可选）",
        value=row.get("annotation_notes", ""),
        max_chars=300,
    )
    if st.button("保存本条并进入下一条", type="primary", use_container_width=True):
        if not annotator_id:
            st.warning("请先填写匿名标注者代号。")
        elif not LABELS[label]:
            st.warning("请选择 0–3 的匹配等级。")
        elif not resume_text:
            st.warning("简历未成功加载，不能保存标签。")
        else:
            row["relevance_label"] = LABELS[label]
            row["label_status"] = "human_labeled"
            row["annotator_id"] = annotator_id
            row["annotated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            row["annotation_confidence"] = confidence
            row["annotation_notes"] = notes
            row["data_status"] = row.get("data_status", "").replace(
                "pending_human", "human_labeled"
            )
            st.success("本条已在当前浏览器会话中保存。请定期下载 CSV，避免会话刷新导致丢失。")
            st.rerun()

    st.download_button(
        "下载当前标注进度 CSV",
        data=export_rows(rows),
        file_name="test_cases_annotated.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(
        "建议由两名标注者独立标注并对分歧复核。当前页面不会把标签自动上传到公共仓库或训练线上模型。"
    )

    with st.expander("查看进度概览"):
        frame = pd.DataFrame(rows)
        st.dataframe(
            frame[["case_id", "split", "resume_position", "jd_title", "relevance_label", "label_status"]],
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    main()
