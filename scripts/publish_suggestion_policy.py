"""人工确认后发布候选建议策略。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="发布经人工复核的建议排序候选策略。")
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--confirm-reviewed", action="store_true")
    args = parser.parse_args()
    if not args.confirm_reviewed:
        raise SystemExit("请人工复核候选策略后添加 --confirm-reviewed。")
    payload = json.loads(args.candidate.read_text(encoding="utf-8"))
    learned_from = int(payload.get("learned_from", 0))
    minimum = int(payload.get("minimum_approved_records", 30))
    if payload.get("status") != "candidate_not_applied" or learned_from < minimum:
        raise SystemExit("候选策略状态或样本量不满足发布要求。")
    payload["status"] = "approved"
    destination = PROJECT_ROOT / "config" / "suggestion_policy.json"
    backup = destination.with_suffix(".previous.json")
    if destination.exists():
        shutil.copy2(destination, backup)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已发布：{destination}")
    print(f"上一版本备份：{backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
