import pytest

from ruyi.ruyipkg.repo import (
    DEFAULT_REPO_ID,
    DEFAULT_REPO_NAME,
    DEFAULT_REPO_PRIORITY,
    RepoEntry,
)


class TestRepoEntry:
    def test_construction(self) -> None:
        entry = RepoEntry(
            id="my-vendor",
            name="My Vendor Overlay",
            remote="https://example.com/overlay.git",
            branch="main",
            local_path=None,
            priority=50,
            active=True,
        )
        assert entry.id == "my-vendor"
        assert entry.name == "My Vendor Overlay"
        assert entry.remote == "https://example.com/overlay.git"
        assert entry.branch == "main"
        assert entry.local_path is None
        assert entry.priority == 50
        assert entry.active is True

    def test_resolve_root_without_local_path(self) -> None:
        entry = RepoEntry(
            id="my-vendor",
            name="My Vendor Overlay",
            remote="https://example.com/overlay.git",
            branch="main",
            local_path=None,
            priority=50,
            active=True,
        )
        root = entry.resolve_root("/home/user/.cache/ruyi")
        assert root == "/home/user/.cache/ruyi/repos/my-vendor"

    def test_resolve_root_with_local_path(self) -> None:
        entry = RepoEntry(
            id="local-testing",
            name="Local Testing",
            remote=None,
            branch="main",
            local_path="/home/user/my-overlay",
            priority=100,
            active=True,
        )
        root = entry.resolve_root("/home/user/.cache/ruyi")
        assert root == "/home/user/my-overlay"

    def test_from_legacy_config(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)
        entry = RepoEntry.from_legacy_config(gc)

        assert entry.id == DEFAULT_REPO_ID
        assert entry.name == DEFAULT_REPO_NAME
        assert entry.priority == DEFAULT_REPO_PRIORITY
        assert entry.active is True
        assert entry.remote is not None
        assert entry.branch == "main"
        assert entry.local_path is None

    def test_from_legacy_config_with_overrides(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc.override_repo_url = "https://custom.example.com/repo.git"
        gc.override_repo_branch = "dev"
        gc.override_repo_dir = "/custom/path"

        entry = RepoEntry.from_legacy_config(gc)

        assert entry.remote == "https://custom.example.com/repo.git"
        assert entry.branch == "dev"
        assert entry.local_path == "/custom/path"

    def test_frozen(self) -> None:
        entry = RepoEntry(
            id="test",
            name="Test",
            remote=None,
            branch="main",
            local_path=None,
            priority=0,
            active=True,
        )
        with pytest.raises(AttributeError):
            entry.id = "changed"  # type: ignore[misc]
