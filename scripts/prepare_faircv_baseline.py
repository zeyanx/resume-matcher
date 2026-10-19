"""按固定种子抽取 FairCV 学术研究样本，不下载或再分发完整数据集。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.faircv import DATASET_ID, DATASET_PAGE, fetch_faircv_rows  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抽取 FairCV 公平性审计基线。")
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "external" / "faircv",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.sample_size <= 10_000:
        raise SystemExit("sample-size 必须在 1 到 10000 之间。")

    first = fetch_faircv_rows(offset=0, length=1)
    population = first.total_rows
    rng = random.Random(args.seed)
    page_size = 100
    population_pages = math.ceil(population / page_size)
    requested_pages = math.ceil(args.sample_size / page_size)
    page_numbers = sorted(rng.sample(range(population_pages), requested_pages))
    records = []
    for page_number in page_numbers:
        page_offset = page_number * page_size
        page_length = min(page_size, population - page_offset)
        records.extend(fetch_faircv_rows(offset=page_offset, length=page_length).records)
    records = records[: args.sample_size]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data_path = args.output_dir / "faircv_academic_sample.jsonl"
    digest = hashlib.sha256()
    with data_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            item = {
                "source_row_index": record.row_index,
                "matching_text": record.matching_text,
                "protected_attributes_for_audit_only": dict(record.protected_attributes),
                "context_attributes": dict(record.context_attributes),
            }
            line = json.dumps(item, ensure_ascii=False, sort_keys=True)
            handle.write(line + "\n")
            digest.update((line + "\n").encode("utf-8"))

    manifest = {
        "dataset_id": DATASET_ID,
        "dataset_page": DATASET_PAGE,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "population_rows_reported_by_api": population,
        "sample_size": args.sample_size,
        "seed": args.seed,
        "sampling_strategy": "reproducible_random_page_cluster_sample",
        "sampled_page_numbers": page_numbers,
        "sample_sha256": digest.hexdigest(),
        "data_status": "synthetic_academic_only",
        "usage": "fairness_audit_and_robustness_testing_only",
        "license_note": "Dataset card states academic research only and prohibits commercial use; no standard machine-readable license was present when integrated.",
        "matching_safety": "Protected attributes are retained only for aggregate audits and removed from matching_text.",
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"样本：{data_path}")
    print(f"清单：{manifest_path}")
    print("仅限学术公平性审计；不得作为真实录用标签或商业训练数据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
