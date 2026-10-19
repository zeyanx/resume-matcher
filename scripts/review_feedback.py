"""列出并人工审核用户反馈；数据库地址只从环境变量读取。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.feedback_store import FeedbackStore, FeedbackStoreError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="人工审核 ResumeMatcher 反馈。")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="列出记录摘要，不显示简历/JD正文。")
    list_parser.add_argument("--status", choices=["pending", "approved", "rejected"])
    list_parser.add_argument("--limit", type=int, default=50)
    subparsers.add_parser("purge", help="按配置保留期删除过期记录。")
    for command in ("approve", "reject", "pending"):
        item = subparsers.add_parser(command, help=f"将记录标记为 {command}。")
        item.add_argument("submission_id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    database_url = os.getenv("FEEDBACK_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("请先设置 FEEDBACK_DATABASE_URL 环境变量。")
    store = FeedbackStore(database_url)
    store.initialize()
    try:
        if args.command == "purge":
            print(f"已删除 {store.purge_expired()} 条过期记录。")
            return 0
        if args.command == "list":
            records = store.list_records(status=args.status, limit=args.limit)
            if not records:
                print("没有记录。")
                return 0
            for record in records:
                comment = str(record["feedback_comment"]).replace("\n", " ")[:80]
                print(
                    f"{record['submission_id']} | {record['created_at']} | "
                    f"{record['review_status']} | 标签={record['relevance_label']} | "
                    f"帮助={record['helpfulness_rating']} | 文本授权="
                    f"{bool(record['research_text_consent'])} | 备注={comment}"
                )
            return 0
        status = "approved" if args.command == "approve" else (
            "rejected" if args.command == "reject" else "pending"
        )
        changed = store.set_review_status(args.submission_id, status)
        print("已更新。" if changed else "未找到记录。")
        return 0 if changed else 1
    except FeedbackStoreError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
