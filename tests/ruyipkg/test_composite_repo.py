import pathlib
from typing import cast
from unittest.mock import MagicMock

import pytest

from ruyi.ruyipkg.composite_repo import CompositeRepo
from ruyi.ruyipkg.repo import DEFAULT_REPO_ID, RepoEntry


def _make_entry(
    repo_id: str = "test-repo",
    priority: int = 0,
    active: bool = True,
    local_path: str | None = None,
) -> RepoEntry:
    return RepoEntry(
        id=repo_id,
        name=f"Test Repo {repo_id}",
        remote="https://example.invalid/repo.git",
        branch="main",
        local_path=local_path,
        priority=priority,
        active=active,
    )


class TestCompositeRepoSingleEntry:
    def test_iter_repos_single(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)
        entry = _make_entry(local_path=str(tmp_path))
        composite = CompositeRepo([entry], gc)

        repos = list(composite.iter_repos())
        assert len(repos) == 1
        assert repos[0].repo_id == "test-repo"

    def test_inactive_entries_excluded(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)
        active_entry = _make_entry(repo_id="active", local_path=str(tmp_path))
        inactive_entry = _make_entry(
            repo_id="inactive", active=False, local_path=str(tmp_path / "other")
        )
        composite = CompositeRepo([active_entry, inactive_entry], gc)

        repos = list(composite.iter_repos())
        assert len(repos) == 1
        assert repos[0].repo_id == "active"

    def test_repo_id_returns_highest_priority(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)
        entry = _make_entry(repo_id="my-repo", priority=50, local_path=str(tmp_path))
        composite = CompositeRepo([entry], gc)

        assert composite.repo_id == "my-repo"

    def test_entries_sorted_by_priority(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)
        low = _make_entry(repo_id="low", priority=0, local_path=str(tmp_path / "low"))
        high = _make_entry(
            repo_id="high", priority=100, local_path=str(tmp_path / "high")
        )
        composite = CompositeRepo([high, low], gc)

        repos = list(composite.iter_repos())
        assert len(repos) == 2
        # Should be sorted ascending by priority
        assert repos[0].repo_id == "low"
        assert repos[1].repo_id == "high"
