import os
import pathlib

import pytest

from ruyi.log import RuyiConsoleLogger
from ruyi.ruyipkg.migration import migrate_repo_dir
from tests.fixtures import MockGlobalModeProvider


@pytest.fixture
def mock_logger() -> RuyiConsoleLogger:
    gm = MockGlobalModeProvider()
    return RuyiConsoleLogger(gm)


class TestMigrateRepoDir:
    def test_migrates_legacy_to_new(
        self, tmp_path: pathlib.Path, mock_logger: RuyiConsoleLogger
    ) -> None:
        cache_root = tmp_path / "cache"
        legacy = cache_root / "packages-index"
        legacy.mkdir(parents=True)
        (legacy / "config.toml").write_text("test")

        migrate_repo_dir(str(cache_root), mock_logger)

        new_path = cache_root / "repos" / "ruyisdk"
        assert new_path.is_dir()
        assert (new_path / "config.toml").read_text() == "test"

        # Legacy path should be a symlink to new
        assert legacy.is_symlink()
        assert os.readlink(str(legacy)) == str(new_path)

    def test_noop_if_legacy_missing(
        self, tmp_path: pathlib.Path, mock_logger: RuyiConsoleLogger
    ) -> None:
        cache_root = tmp_path / "cache"
        cache_root.mkdir(parents=True)

        migrate_repo_dir(str(cache_root), mock_logger)

        assert not (cache_root / "repos" / "ruyisdk").exists()

    def test_noop_if_already_migrated(
        self, tmp_path: pathlib.Path, mock_logger: RuyiConsoleLogger
    ) -> None:
        cache_root = tmp_path / "cache"
        new_path = cache_root / "repos" / "ruyisdk"
        new_path.mkdir(parents=True)
        (new_path / "config.toml").write_text("new")

        # Legacy exists as a regular dir too
        legacy = cache_root / "packages-index"
        legacy.mkdir(parents=True)
        (legacy / "config.toml").write_text("old")

        migrate_repo_dir(str(cache_root), mock_logger)

        # Neither should be changed
        assert (new_path / "config.toml").read_text() == "new"
        assert not legacy.is_symlink()
        assert (legacy / "config.toml").read_text() == "old"

    def test_noop_if_legacy_is_symlink(
        self, tmp_path: pathlib.Path, mock_logger: RuyiConsoleLogger
    ) -> None:
        cache_root = tmp_path / "cache"
        new_path = cache_root / "repos" / "ruyisdk"
        new_path.mkdir(parents=True)
        (new_path / "config.toml").write_text("data")

        legacy = cache_root / "packages-index"
        os.symlink(str(new_path), str(legacy))

        migrate_repo_dir(str(cache_root), mock_logger)

        # Symlink still points correctly
        assert legacy.is_symlink()
        assert (legacy / "config.toml").read_text() == "data"
