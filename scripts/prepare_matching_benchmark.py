"""构建 FairCV 简历 + 公开中文 JD 的待人工标注评估集。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics.pairwise import cosine_similarity  # noqa: E402

from models.bge_matcher import load_bge_model, split_text_for_embedding  # noqa: E402
from models.experience_matcher import calculate_experience_match  # noqa: E402
from models.tfidf_matcher import calculate_tfidf_similarity  # noqa: E402
from utils.benchmark_data import (  # noqa: E402
    JD_DATASET_ID,
    JD_DATASET_PAGE,
    JD_LICENSE,
    JD_SOURCE_FILE,
    JD_SOURCE_URL,
    choose_evenly_spaced,
    load_job_descriptions,
)
from utils.faircv import (  # noqa: E402
    DATASET_ID,
    DATASET_PAGE,
    FairCVError,
    FairCVRecord,
    fetch_faircv_rows,
)
from utils.skill_extractor import analyze_skill_gap  # noqa: E402


DEFAULT_RESUME_COUNT = 60
DEFAULT_PAIRS_PER_RESUME = 5
DEFAULT_SEED = 20261019
PAIR_COLUMNS = (
    "case_id",
    "query_id",
    "resume_id",
    "resume_source_row_index",
    "resume_position",
    "resume_skill_level",
    "jd_id",
    "jd_source_row_index",
    "jd_source_job_id",
    "jd_title",
    "jd_text",
    "split",
    "relevance_label",
    "label_status",
    "annotator_id",
    "annotated_at",
    "tfidf_score",
    "semantic_score",
    "skill_score",
    "experience_score",
    "job_category",
    "data_status",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-count", type=int, default=DEFAULT_RESUME_COUNT)
    parser.add_argument("--pairs-per-resume", type=int, default=DEFAULT_PAIRS_PER_RESUME)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--jd-source",
        type=Path,
        default=PROJECT_ROOT / "data" / "external" / "job_descriptions" / "source_test.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "test_cases.csv",
    )
    parser.add_argument(
        "--external-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "external" / "matching_benchmark",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=PROJECT_ROOT / "models_cache" / "bge-small-zh-v1.5",
    )
    parser.add_argument("--skip-bge", action="store_true")
    return parser.parse_args()


def download_file(url: str, destination: Path) -> None:
    """下载公开数据文件；已有的非空文件会直接复用。"""
    if destination.is_file() and destination.stat().st_size > 0:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "ResumeMatcher-Academic-Benchmark/1.0"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as handle:
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)


def collect_diverse_resumes(count: int, seed: int) -> tuple[FairCVRecord, ...]:
    """按随机页抽样并限制单岗位占比，获得岗位和水平更分散的简历。"""
    if not 50 <= count <= 100:
        raise ValueError("resume-count 必须在 50 到 100 之间。")
    def fetch_with_retry(offset: int, length: int):
        last_error: Exception | None = None
        for attempt in range(6):
            try:
                return fetch_faircv_rows(offset=offset, length=length, timeout_seconds=45)
            except FairCVError as exc:
                last_error = exc
                if attempt < 5:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"FairCV 页面 {offset} 连续读取失败。") from last_error

    total_rows = fetch_with_retry(offset=0, length=1).total_rows
    page_size = 100
    total_pages = math.ceil(total_rows / page_size)
    rng = random.Random(seed)
    page_numbers = rng.sample(range(total_pages), 48)

    def fetch(page_number: int):
        offset = page_number * page_size
        # 只需每个随机页的少量记录；较小响应可显著降低大文本传输中断概率。
        length = min(10, total_rows - offset)
        return page_number, fetch_with_retry(offset=offset, length=length).records

    with ThreadPoolExecutor(max_workers=2) as pool:
        pages = sorted(pool.map(fetch, page_numbers), key=lambda item: page_numbers.index(item[0]))

    by_position: dict[str, list[FairCVRecord]] = {}
    for _, records in pages:
        for record in records:
            position = str(record.context_attributes.get("position") or "未分类").strip()
            by_position.setdefault(position, []).append(record)

    positions = list(by_position)
    rng.shuffle(positions)
    selected: list[FairCVRecord] = []
    per_position_limit = max(1, math.ceil(count / min(20, len(positions))))
    for position in positions:
        candidates = by_position[position]
        rng.shuffle(candidates)
        levels_seen: set[str] = set()
        ordered = sorted(
            candidates,
            key=lambda item: str(item.context_attributes.get("skill_level")) in levels_seen,
        )
        for record in ordered[:per_position_limit]:
            selected.append(record)
            levels_seen.add(str(record.context_attributes.get("skill_level") or ""))
            if len(selected) == count:
                return tuple(selected)
    if len(selected) < count:
        existing = {item.row_index for item in selected}
        remainder = [item for values in by_position.values() for item in values if item.row_index not in existing]
        rng.shuffle(remainder)
        selected.extend(remainder[: count - len(selected)])
    if len(selected) != count:
        raise RuntimeError(f"只取得 {len(selected)} 份合格 FairCV 简历。")
    return tuple(selected)


def choose_jobs(path: Path, count: int, seed: int):
    records = list(load_job_descriptions(path))
    rng = random.Random(seed)
    rng.shuffle(records)
    return choose_evenly_spaced(records, count)


def assign_jobs(resumes, jobs, pairs_per_resume: int):
    """以未使用 JD 的相似度分位点构造候选池，不生成相关性标签。"""
    resume_texts = [item.matching_text for item in resumes]
    job_texts = [item.matching_text for item in jobs]
    vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 4), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(resume_texts + job_texts)
    similarities = cosine_similarity(matrix[: len(resumes)], matrix[len(resumes) :])
    available = set(range(len(jobs)))
    assignments: list[tuple[int, int]] = []
    quantiles = np.linspace(0.95, 0.05, pairs_per_resume)
    for resume_index in range(len(resumes)):
        ranked = sorted(available, key=lambda index: similarities[resume_index, index])
        selected: list[int] = []
        for quantile in quantiles:
            if not ranked:
                break
            index = ranked[round((len(ranked) - 1) * quantile)]
            selected.append(index)
            ranked.remove(index)
            available.remove(index)
        assignments.extend((resume_index, job_index) for job_index in selected)
    if available or len(assignments) != len(resumes) * pairs_per_resume:
        raise RuntimeError("JD 分配未能覆盖预期的全部配对。")
    return tuple(assignments)


def encode_documents(model, texts: list[str]) -> np.ndarray:
    """与在线匹配器一致：分块编码、块均值、再归一化。"""
    all_chunks: list[str] = []
    owners: list[int] = []
    for owner, text in enumerate(texts):
        chunks = split_text_for_embedding(text)
        if not chunks:
            raise ValueError("评估文本不能为空。")
        all_chunks.extend(chunks)
        owners.extend([owner] * len(chunks))
    embeddings = np.asarray(
        model.encode(
            all_chunks,
            batch_size=16,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ),
        dtype=np.float32,
    )
    vectors = np.zeros((len(texts), embeddings.shape[1]), dtype=np.float32)
    counts = np.zeros(len(texts), dtype=np.int32)
    for owner, vector in zip(owners, embeddings):
        vectors[owner] += vector
        counts[owner] += 1
    vectors /= counts[:, None]
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def write_external_payload(path: Path, resumes, jobs) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in resumes:
            item = {
                "kind": "resume",
                "id": f"faircv-{record.row_index}",
                "source_row_index": record.row_index,
                "text": record.matching_text,
                "context": dict(record.context_attributes),
            }
            line = json.dumps(item, ensure_ascii=False, sort_keys=True)
            handle.write(line + "\n")
            digest.update((line + "\n").encode("utf-8"))
        for record in jobs:
            item = {
                "kind": "jd",
                "id": f"jd-{record.source_row_index}",
                "source_row_index": record.source_row_index,
                "source_job_id": record.source_job_id,
                "title": record.title,
                "text": record.matching_text,
            }
            line = json.dumps(item, ensure_ascii=False, sort_keys=True)
            handle.write(line + "\n")
            digest.update((line + "\n").encode("utf-8"))
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    if args.pairs_per_resume < 2:
        raise SystemExit("pairs-per-resume 至少为 2。")
    jd_count = args.resume_count * args.pairs_per_resume
    if not 200 <= jd_count <= 500:
        raise SystemExit("JD 数量必须在 200 到 500 之间。")

    download_file(JD_SOURCE_URL, args.jd_source)
    resumes = collect_diverse_resumes(args.resume_count, args.seed)
    jobs = choose_jobs(args.jd_source, jd_count, args.seed)
    assignments = assign_jobs(resumes, jobs, args.pairs_per_resume)

    texts = [item.matching_text for item in resumes] + [item.matching_text for item in jobs]
    semantic_matrix = None
    if not args.skip_bge:
        model = load_bge_model(local_model_path=str(args.model_path), offline=True, device="cpu")
        semantic_matrix = encode_documents(model, texts)

    validation_queries = max(1, round(args.resume_count * 0.2))
    rows: list[dict[str, object]] = []
    for case_number, (resume_index, job_index) in enumerate(assignments, start=1):
        resume = resumes[resume_index]
        job = jobs[job_index]
        tfidf = calculate_tfidf_similarity(resume.matching_text, job.matching_text)
        skills = analyze_skill_gap(resume.matching_text, job.matching_text)
        experience = calculate_experience_match(resume.matching_text, job.matching_text)
        semantic = ""
        if semantic_matrix is not None:
            semantic = float(
                np.clip(
                    np.dot(semantic_matrix[resume_index], semantic_matrix[len(resumes) + job_index]),
                    0.0,
                    1.0,
                )
            )
        split = "validation" if resume_index < validation_queries else "test"
        rows.append(
            {
                "case_id": f"case-{case_number:04d}",
                "query_id": f"faircv-{resume.row_index}",
                "resume_id": f"faircv-{resume.row_index}",
                "resume_source_row_index": resume.row_index,
                "resume_position": resume.context_attributes.get("position") or "未分类",
                "resume_skill_level": resume.context_attributes.get("skill_level") or "未标注",
                "jd_id": f"jd-{job.source_row_index}",
                "jd_source_row_index": job.source_row_index,
                "jd_source_job_id": job.source_job_id,
                "jd_title": job.title,
                "jd_text": job.matching_text,
                "split": split,
                "relevance_label": "",
                "label_status": "pending_human",
                "annotator_id": "",
                "annotated_at": "",
                "tfidf_score": tfidf,
                "semantic_score": semantic,
                "skill_score": skills.coverage_rate,
                "experience_score": experience.score,
                "job_category": resume.context_attributes.get("position") or "未分类",
                "data_status": "faircv_synthetic_resume_public_jd_pending_human",
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    payload_path = args.external_dir / "annotation_payload.jsonl"
    payload_sha256 = write_external_payload(payload_path, resumes, jobs)
    selected_resumes = []
    used_positions: set[str] = set()
    for resume in resumes:
        position = str(resume.context_attributes.get("position") or "未分类")
        if position in used_positions:
            continue
        matching_case = next(row for row in rows if row["resume_id"] == f"faircv-{resume.row_index}")
        selected_resumes.append(
            {
                "id": f"faircv-{resume.row_index}",
                "label": f"{position}（{resume.context_attributes.get('skill_level') or '未标注'}级）",
                "source_row_index": resume.row_index,
                "position": position,
                "skill_level": resume.context_attributes.get("skill_level") or "未标注",
                "default_jd_id": matching_case["jd_id"],
            }
        )
        used_positions.add(position)
        if len(selected_resumes) == 5:
            break
    examples_path = PROJECT_ROOT / "data" / "sample_resumes" / "faircv_examples.json"
    examples_path.write_text(json.dumps(selected_resumes, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": args.seed,
        "resume_count": len(resumes),
        "resume_position_count": len({row["resume_position"] for row in rows}),
        "jd_count": len(jobs),
        "pair_count": len(rows),
        "pairs_per_resume": args.pairs_per_resume,
        "validation_pair_count": sum(row["split"] == "validation" for row in rows),
        "test_pair_count": sum(row["split"] == "test" for row in rows),
        "faircv": {"dataset_id": DATASET_ID, "dataset_page": DATASET_PAGE},
        "job_descriptions": {
            "dataset_id": JD_DATASET_ID,
            "dataset_page": JD_DATASET_PAGE,
            "source_file": JD_SOURCE_FILE,
            "license": JD_LICENSE,
        },
        "selection_note": "TF-IDF 分位点只用于构造难度不同的候选池，不是标签。",
        "label_status": "pending_human",
        "evaluation_blocked_until": "所有 relevance_label 经真人判断并将 label_status 改为 human_labeled",
        "semantic_scores": "bge-small-zh-v1.5" if semantic_matrix is not None else "not_computed",
        "external_payload_sha256": payload_sha256,
    }
    args.external_dir.mkdir(parents=True, exist_ok=True)
    (args.external_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
