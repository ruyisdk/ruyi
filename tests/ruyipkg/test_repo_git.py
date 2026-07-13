"""Tests for ``MetadataRepo.ensure_git_repo`` handling of on-disk cache states.

These regression tests cover https://github.com/ruyisdk/ruyi/issues/415: a
package-index directory that exists on disk but is not a valid Git repository
(e.g. an empty directory left by an interrupted first clone, or a corrupt cache
left by a timeout-killed ``ruyi update``) used to make pygit2 raise an uncaught
``GitError`` with no diagnostic logging.
"""

import io
import pathlib
from typing import cast

import pytest
from pygit2 import Repository

from ruyi.config import GlobalConfig
from ruyi.log import RuyiConsoleLogger
from ruyi.ruyipkg.repo import MetadataRepo

from tests.fixtures import MockGlobalModeProvider, MockRepository


def _make_repo(
    root: pathlib.Path,
    *,
    is_debug: bool = False,
) -> tuple[MetadataRepo, io.StringIO]:
    stderr = io.StringIO()
    gm = MockGlobalModeProvider(is_debug=is_debug)
    logger = RuyiConsoleLogger(gm, stdout=io.StringIO(), stderr=stderr)
    gc = GlobalConfig(gm, logger)
    repo = MetadataRepo(
        gc,
        root=str(root),
        remote="https://example.invalid/packages-index.git",
        branch="main",
    )
    return repo, stderr


class TestEnsureGitRepoInvalidCache:
    def test_empty_dir_is_recloned(
        self,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = tmp_path / "packages-index"
        root.mkdir()  # exists but empty: as-good-as-not-present

        clone_calls: list[str] = []

        def _fake_clone(url: str, path: str, **_kwargs: object) -> Repository:
            clone_calls.append(path)
            pathlib.Path(path).mkdir(parents=True, exist_ok=True)
            return cast(Repository, MockRepository(pathlib.Path(path)))

        monkeypatch.setattr("ruyi.ruyipkg.repo.clone_repository", _fake_clone)

        repo, _stderr = _make_repo(root)
        result = repo.ensure_git_repo()

        assert result is not None
        assert clone_calls == [str(root)]

    def test_corrupt_dir_is_fatal(
        self,
        tmp_path: pathlib.Path,
    ) -> None:
        # A non-empty directory without valid Git metadata. This is what both a
        # corrupt cache and a timeout-killed clone look like to pygit2.
        root = tmp_path / "packages-index"
        root.mkdir()
        (root / "stray-file").write_text("leftover\n", encoding="utf-8")

        repo, stderr = _make_repo(root)

        with pytest.raises(SystemExit):
            repo.ensure_git_repo()

        fatal_lines = [
            line
            for line in stderr.getvalue().splitlines()
            if line.startswith("fatal error: ")
        ]
        assert fatal_lines
        assert any(str(root) in line for line in fatal_lines)
