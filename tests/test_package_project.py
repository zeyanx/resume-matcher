"""最终项目 ZIP 打包与安全校验测试。"""

import json
from zipfile import ZipFile

from scripts.package_project import ARCHIVE_ROOT, create_archive, validate_archive


def test_project_archive_contains_required_files_and_excludes_cache(tmp_path) -> None:
    archive_path, checksum_path = create_archive(tmp_path / "ResumeMatcher.zip")
    result = validate_archive(archive_path)
    assert result["crc_ok"]
    assert result["required_files_ok"]
    assert checksum_path.exists()

    with ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert f"{ARCHIVE_ROOT}/README.md" in names
        assert f"{ARCHIVE_ROOT}/PACKAGE_MANIFEST.json" in names
        assert any(name.startswith(f"{ARCHIVE_ROOT}/reports/stage7_synthetic_demo/") for name in names)
        assert not any("models_cache" in name for name in names)
        assert not any("__pycache__" in name for name in names)
        manifest = json.loads(archive.read(f"{ARCHIVE_ROOT}/PACKAGE_MANIFEST.json"))
        assert manifest["project"] == ARCHIVE_ROOT
        assert manifest["files"]
