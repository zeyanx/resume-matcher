"""从人工审核通过的反馈离线生成候选融合权重，不修改线上配置。"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.weight_search import (  # noqa: E402
    LabeledScoreCase,
    run_weight_grid_search,
    save_weight_search_result,
)
from utils.feedback_store import FeedbackStore  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="离线学习候选融合权重。")
    parser.add_argument("--minimum-records", type=int, default=30)
    parser.add_argument("--step", type=float, default=0.1)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "reports" / "feedback_learning",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.minimum_records < 3:
        raise SystemExit("minimum-records 不能小于 3。")
    database_url = os.getenv("FEEDBACK_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("请先设置 FEEDBACK_DATABASE_URL 环境变量。")

    store = FeedbackStore(database_url)
    store.initialize()
    rows = store.approved_learning_rows()
    if len(rows) < args.minimum_records:
        raise SystemExit(
            f"人工审核通过且子分数完整的记录只有 {len(rows)} 条；"
            f"至少需要 {args.minimum_records} 条。"
        )
    cases = tuple(
        LabeledScoreCase(
            case_id=str(row["submission_id"]),
            split=str(row["split"]),
            relevance_label=float(row["relevance_label"]),
            semantic_score=float(row["semantic_score"]),
            skill_score=float(row["skill_score"]),
            experience_score=float(row["experience_score"]),
            data_status="approved_user_feedback",
        )
        for row in rows
    )
    result = run_weight_grid_search(cases, step=args.step)
    summary_path, comparison_path = save_weight_search_result(result, args.output_dir)
    print(f"候选权重：{summary_path}")
    print(f"验证集比较：{comparison_path}")
    print("未修改 config/fusion_weights.json；请人工复核候选结果。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
