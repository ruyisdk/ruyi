"""Tests for package manifest discovery in metadata repositories."""

import io
import pathlib

import pygit2

from ruyi.config import GlobalConfig
from ruyi.log import RuyiConsoleLogger
from ruyi.ruyipkg.repo import MetadataRepo

from tests.fixtures import MockGlobalModeProvider


def _make_repo(root: pathlib.Path) -> MetadataRepo:
    gm = MockGlobalModeProvider(is_debug=False)
    logger = RuyiConsoleLogger(gm, stdout=io.StringIO(), stderr=io.StringIO())
    gc = GlobalConfig(gm, logger)
    return MetadataRepo(
        gc,
        root=str(root),
        remote="https://example.invalid/packages-index.git",
        branch="main",
    )


def _write_manifest(root: pathlib.Path, ver: str) -> pathlib.Path:
    pkg_dir = root / "packages" / "toolchain" / "gcc"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    path = pkg_dir / f"{ver}.toml"
    path.write_text(
        "\n".join(
            [
                'format = "v1"',
                'kind = ["source"]',
                "distfiles = []",
                "",
                "[metadata]",
                'desc = "test package"',
                "",
                "[metadata.vendor]",
                'name = "test-vendor"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_invalid_semver_filename_is_ignored(tmp_path: pathlib.Path) -> None:
    """A manifest file name that is not valid SemVer must not crash ruyi."""

    pygit2.init_repository(str(tmp_path))
    _write_manifest(tmp_path, "0.1.2.ruyi-20261111")
    _write_manifest(tmp_path, "0.1.2-ruyi.20261112")

    repo = _make_repo(tmp_path)
    manifests = list(repo.iter_pkg_manifests())

    assert [pm.ver for pm in manifests] == ["0.1.2-ruyi.20261112"]
