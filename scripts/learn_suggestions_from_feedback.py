"""从人工审核通过的满意度反馈生成建议排序候选策略。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.suggestion_feedback_learning import (  # noqa: E402
    save_candidate_policy,
    train_suggestion_policy,
)
from utils.feedback_store import FeedbackStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="离线训练建议满意度候选排序策略。")
    parser.add_argument("--minimum-records", type=int, default=30)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "suggestion_feedback_learning",
    )
    args = parser.parse_args()
    if args.minimum_records < 10:
        raise SystemExit("minimum-records 不能小于 10。")
    database_url = os.getenv("FEEDBACK_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("请先设置 FEEDBACK_DATABASE_URL 环境变量。")
    store = FeedbackStore(database_url)
    store.initialize()
    try:
        result = train_suggestion_policy(
            store.approved_suggestion_learning_rows(),
            minimum_records=args.minimum_records,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    candidate_path, metrics_path = save_candidate_policy(
        result, args.output_dir, args.minimum_records
    )
    print(f"候选策略：{candidate_path}")
    print(f"隔离测试指标：{metrics_path}")
    print("未修改 config/suggestion_policy.json；审核候选策略后再人工发布。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
