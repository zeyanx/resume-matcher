"""创建可移植、可校验且不包含本地模型缓存的项目 ZIP。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "ResumeMatcher"
EXCLUDED_DIRECTORIES = {
    ".git",
    ".cache",
    ".pytest_cache",
    ".pytest_tmp",
    ".venv",
    "__pycache__",
    "models_cache",
    "private",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}
EXCLUDED_FILES = {".env", ".streamlit/secrets.toml"}
REQUIRED_PATHS = {
    "README.md",
    "requirements.txt",
    "environment.yml",
    "app.py",
    "data/skills.json",
    "data/sample_resumes/sample_resume.txt",
    "data/sample_jds/sample_python_backend.txt",
    "data/evaluation/labeled_scores_template.csv",
    "models/tfidf_matcher.py",
    "models/bge_matcher.py",
    "models/fusion_matcher.py",
    "models/suggestion.py",
    "pages/2_技能差距分析.py",
    "pages/3_简历优化建议.py",
    "pages/4_评估实验.py",
    "pages/5_数据与隐私.py",
    "evaluation/evaluate.py",
    "utils/feedback_config.py",
    "utils/feedback_store.py",
    "PRIVACY.md",
    "DEPLOYMENT.md",
    "THESIS_OUTLINE.md",
    "EXPERIMENT_CHAPTER_MATERIAL.md",
    "DEFENSE_DEMO_SCRIPT.md",
}


def should_include(path: Path) -> bool:
    """过滤缓存、模型、私有数据和临时文件。"""
    relative = path.relative_to(PROJECT_ROOT)
    if relative.as_posix() == "PACKAGE_MANIFEST.json":
        return False
    if relative.as_posix() in EXCLUDED_FILES:
        return False
    if any(part in EXCLUDED_DIRECTORIES for part in relative.parts):
        return False
    return path.is_file() and path.suffix.lower() not in EXCLUDED_SUFFIXES


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_files() -> tuple[Path, ...]:
    """按相对路径排序，确保清单稳定。"""
    return tuple(
        sorted(
            (path for path in PROJECT_ROOT.rglob("*") if should_include(path)),
            key=lambda path: path.relative_to(PROJECT_ROOT).as_posix(),
        )
    )


def validate_source(files: tuple[Path, ...]) -> None:
    included = {path.relative_to(PROJECT_ROOT).as_posix() for path in files}
    missing = sorted(REQUIRED_PATHS - included)
    if missing:
        raise RuntimeError(f"项目缺少必须文件：{', '.join(missing)}")


def validate_archive(archive_path: Path) -> dict[str, object]:
    """检查 ZIP CRC、危险路径、必须文件和本地缓存排除状态。"""
    with ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"ZIP CRC 校验失败：{bad_member}")
        names = archive.namelist()
        for name in names:
            member = PurePosixPath(name)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"ZIP 包含不安全路径：{name}")
        required_archive_paths = {f"{ARCHIVE_ROOT}/{path}" for path in REQUIRED_PATHS}
        missing = sorted(required_archive_paths - set(names))
        if missing:
            raise RuntimeError(f"ZIP 缺少必须文件：{', '.join(missing)}")
        forbidden = [
            name
            for name in names
            if any(part in EXCLUDED_DIRECTORIES for part in PurePosixPath(name).parts)
        ]
        if forbidden:
            raise RuntimeError(f"ZIP 错误包含缓存或私有目录：{forbidden[0]}")
    return {"file_count": len(names), "crc_ok": True, "required_files_ok": True}


def create_archive(output_path: Path) -> tuple[Path, Path]:
    """创建 ZIP，内嵌文件哈希清单，并写出 ZIP 自身校验文件。"""
    files = collect_files()
    validate_source(files)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "project": ARCHIVE_ROOT,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "excluded": sorted(EXCLUDED_DIRECTORIES),
        "files": [
            {
                "path": path.relative_to(PROJECT_ROOT).as_posix(),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
            for path in files
        ],
    }
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            archive.write(path, f"{ARCHIVE_ROOT}/{relative}")
        archive.writestr(
            f"{ARCHIVE_ROOT}/PACKAGE_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    validation = validate_archive(output_path)
    checksum = file_sha256(output_path)
    checksum_path = output_path.with_suffix(output_path.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {output_path.name}\n", encoding="ascii")
    print(f"ZIP：{output_path}")
    print(f"SHA-256：{checksum}")
    print(f"文件数：{validation['file_count']}")
    print("CRC 校验：通过")
    print("必须文件检查：通过")
    return output_path, checksum_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="打包并校验 ResumeMatcher 工程。")
    parser.add_argument("--output", type=Path, required=True, help="目标 ZIP 路径。")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    create_archive(arguments.output.resolve())
