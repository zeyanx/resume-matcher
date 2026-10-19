"""扫描本地 FairCV 学术样本，按受控候选表扩充技能词典。"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = (
    {"canonical": "Kafka", "category": "数据与中间件", "aliases": ["kafka", "apache kafka"]},
    {"canonical": "RabbitMQ", "category": "数据与中间件", "aliases": ["rabbitmq", "rabbit mq"]},
    {"canonical": "Apache Spark", "category": "大数据", "aliases": ["apache spark", "spark"]},
    {"canonical": "Hadoop", "category": "大数据", "aliases": ["hadoop", "apache hadoop"]},
    {"canonical": "Apache Flink", "category": "大数据", "aliases": ["apache flink", "flink"]},
    {"canonical": "XGBoost", "category": "数据与算法", "aliases": ["xgboost", "xg boost"]},
    {"canonical": "Keras", "category": "数据与算法", "aliases": ["keras"]},
    {"canonical": "Spring Cloud", "category": "后端开发", "aliases": ["spring cloud", "springcloud"]},
    {"canonical": "Gin", "category": "后端开发", "aliases": ["gin", "gin框架", "gin framework"]},
    {"canonical": "Beego", "category": "后端开发", "aliases": ["beego"]},
    {"canonical": "Istio", "category": "工程与运维", "aliases": ["istio", "service mesh"]},
    {"canonical": "Kotlin", "category": "编程语言", "aliases": ["kotlin"]},
    {"canonical": "Android", "category": "移动开发", "aliases": ["android", "安卓"]},
    {"canonical": "iOS", "category": "移动开发", "aliases": ["ios", "iphone os"]},
    {"canonical": "Scrum", "category": "工程协作", "aliases": ["scrum", "敏捷开发"]},
    {"canonical": "Jira", "category": "工程协作", "aliases": ["jira"]},
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inputs",
        type=Path,
        nargs="+",
        default=[
            PROJECT_ROOT / "data" / "external" / "faircv" / "faircv_academic_sample.jsonl",
            PROJECT_ROOT
            / "data"
            / "external"
            / "matching_benchmark"
            / "annotation_payload.jsonl",
        ],
    )
    parser.add_argument("--minimum-documents", type=int, default=3)
    parser.add_argument("--catalog", type=Path, default=PROJECT_ROOT / "data" / "skills.json")
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "data" / "skills_faircv_corpus_report.json",
    )
    return parser.parse_args()


def read_resume_texts(paths: list[Path]) -> tuple[tuple[str, str], ...]:
    texts: dict[str, str] = {}
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("kind") not in {None, "resume"}:
                continue
            identifier = str(item.get("id") or item.get("source_row_index"))
            text = str(item.get("text") or item.get("matching_text") or "")
            if text:
                texts[identifier] = text
    return tuple(sorted(texts.items()))


def document_frequency(texts: tuple[tuple[str, str], ...]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for candidate in CANDIDATES:
        aliases = [str(alias) for alias in candidate["aliases"]]
        pattern = re.compile(
            r"(?<![a-z0-9])(?:" + "|".join(re.escape(alias) for alias in aliases) + r")(?![a-z0-9])",
            re.IGNORECASE,
        )
        counts[str(candidate["canonical"])] = sum(bool(pattern.search(text)) for _, text in texts)
    return counts


def main() -> int:
    args = parse_args()
    texts = read_resume_texts(list(args.inputs))
    if not texts:
        raise SystemExit("没有找到可扫描的本地 FairCV 简历样本。")
    counts = document_frequency(texts)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    existing = {str(item["canonical"]).casefold() for item in catalog["skills"]}
    added: list[str] = []
    for candidate in CANDIDATES:
        canonical = str(candidate["canonical"])
        if counts[canonical] < args.minimum_documents or canonical.casefold() in existing:
            continue
        catalog["skills"].append(candidate)
        existing.add(canonical.casefold())
        added.append(canonical)
    catalog["version"] = "1.1.0"
    catalog["description"] = (
        "ResumeMatcher 中文岗位技能词典；canonical 为统一展示名称，aliases 为可识别同义词。"
        "新增项来自本地 FairCV 学术样本的受控候选扫描，非自动生成。"
    )
    args.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": "本地已抽取的 FairCV 学术样本（去重后）",
        "document_count": len(texts),
        "full_faircv_scan": False,
        "scope_note": "未下载并扫描 FairCV 全量 6GB 数据；报告不得描述为全量词频。",
        "minimum_document_frequency": args.minimum_documents,
        "document_frequencies": dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
        "added_to_catalog": added,
        "method": "只统计预先审核的技术词及其同义词，不从文本自动创造技能名。",
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
