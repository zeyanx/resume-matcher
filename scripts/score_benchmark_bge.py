"""为既有待标注评估集批量计算 BGE 分数，避免重复下载源数据。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402

from models.bge_matcher import load_bge_model  # noqa: E402
from models.experience_matcher import calculate_experience_match  # noqa: E402
from models.tfidf_matcher import calculate_tfidf_similarity  # noqa: E402
from scripts.prepare_matching_benchmark import PAIR_COLUMNS, encode_documents  # noqa: E402
from utils.faircv import remove_protected_content  # noqa: E402
from utils.feedback_store import redact_personal_data  # noqa: E402
from utils.skill_extractor import analyze_skill_gap  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data" / "test_cases.csv")
    parser.add_argument(
        "--payload",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "external"
        / "matching_benchmark"
        / "annotation_payload.jsonl",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=PROJECT_ROOT / "models_cache" / "bge-small-zh-v1.5",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload: dict[str, str] = {}
    for line in args.payload.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        text = str(item["text"])
        if item.get("kind") == "resume":
            text = remove_protected_content(text)
        elif item.get("kind") == "jd":
            text = redact_personal_data(text)
        payload[str(item["id"])] = text
    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    document_ids = sorted(
        {str(row["resume_id"]) for row in rows} | {str(row["jd_id"]) for row in rows}
    )
    missing = [document_id for document_id in document_ids if document_id not in payload]
    if missing:
        raise SystemExit(f"外部文本载荷缺少 {len(missing)} 个文档。")
    model = load_bge_model(local_model_path=str(args.model_path), offline=True, device="cpu")
    vectors = encode_documents(model, [payload[document_id] for document_id in document_ids])
    index = {document_id: position for position, document_id in enumerate(document_ids)}
    for row in rows:
        row["jd_text"] = redact_personal_data(row["jd_text"])
        resume_text = payload[row["resume_id"]]
        jd_text = row["jd_text"]
        row["tfidf_score"] = calculate_tfidf_similarity(resume_text, jd_text)
        row["skill_score"] = analyze_skill_gap(resume_text, jd_text).coverage_rate
        row["experience_score"] = calculate_experience_match(resume_text, jd_text).score
        score = np.dot(vectors[index[row["resume_id"]]], vectors[index[row["jd_id"]]])
        row["semantic_score"] = float(np.clip(score, 0.0, 1.0))
    with args.input.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"已写入 {len(rows)} 条 BGE 分数：{args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
