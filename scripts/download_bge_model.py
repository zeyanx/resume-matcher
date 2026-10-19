"""下载 BGE 模型并保存为可离线加载的本地目录。"""

from __future__ import annotations

import argparse
from pathlib import Path

from sentence_transformers import SentenceTransformer


MODEL_NAME = "BAAI/bge-small-zh-v1.5"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    """读取命令行参数。"""
    parser = argparse.ArgumentParser(description="下载并保存 ResumeMatcher 使用的 BGE 模型")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "models_cache" / "bge-small-zh-v1.5",
        help="离线模型输出目录",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=PROJECT_ROOT / "models_cache" / "huggingface",
        help="Hugging Face 下载缓存目录",
    )
    return parser.parse_args()


def main() -> None:
    """在线下载模型，并保存标准 SentenceTransformer 本地副本。"""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"正在下载模型：{MODEL_NAME}")
    model = SentenceTransformer(
        MODEL_NAME,
        cache_folder=str(args.cache_dir),
        device="cpu",
        trust_remote_code=False,
    )
    model.save(str(args.output_dir))
    print(f"离线模型已保存到：{args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
