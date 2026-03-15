"""Tests for [[repos]] config parsing and validation."""

from typing import TYPE_CHECKING

import pytest

from ruyi.config import GlobalConfig

if TYPE_CHECKING:
    from tests.fixtures import MockGlobalModeProvider
    from ruyi.log import RuyiLogger


class TestReposConfigParsing:
    def test_no_repos_section(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        # Only the default entry should be present.
        assert len(gc.repo_entries) == 1
        assert gc.repo_entries[0].id == "ruyisdk"

    def test_single_extra_repo(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "my-vendor",
                        "remote": "https://example.invalid/repo.git",
                        "priority": 50,
                    }
                ]
            },
            is_global_scope=False,
        )
        # Clear cached property to pick up the new entries.
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        assert len(gc.repo_entries) == 2
        ids = [e.id for e in gc.repo_entries]
        assert "ruyisdk" in ids
        assert "my-vendor" in ids

    def test_repos_sorted_by_priority(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "high-prio",
                        "remote": "https://example.invalid/high.git",
                        "priority": 100,
                    },
                    {
                        "id": "low-prio",
                        "remote": "https://example.invalid/low.git",
                        "priority": -10,
                    },
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        entries = gc.repo_entries
        assert len(entries) == 3
        # Should be sorted by priority ascending.
        priorities = [e.priority for e in entries]
        assert priorities == sorted(priorities)

    def test_rejects_invalid_id(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "INVALID-CAPS",
                        "remote": "https://example.invalid/repo.git",
                    },
                    {
                        "id": "",
                        "remote": "https://example.invalid/repo.git",
                    },
                    {
                        "id": "-starts-with-dash",
                        "remote": "https://example.invalid/repo.git",
                    },
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        # None of the invalid entries should be added.
        assert len(gc.repo_entries) == 1
        assert gc.repo_entries[0].id == "ruyisdk"

    def test_rejects_reserved_id(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "ruyisdk",
                        "remote": "https://example.invalid/repo.git",
                        "priority": 999,
                    }
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        # Should still have only the default entry.
        assert len(gc.repo_entries) == 1
        assert gc.repo_entries[0].id == "ruyisdk"
        assert gc.repo_entries[0].priority == 0  # unmodified

    def test_rejects_duplicate_ids(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "vendor-a",
                        "remote": "https://example.invalid/a.git",
                        "priority": 10,
                    },
                    {
                        "id": "vendor-a",
                        "remote": "https://example.invalid/a-dup.git",
                        "priority": 20,
                    },
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        vendor_entries = [e for e in gc.repo_entries if e.id == "vendor-a"]
        assert len(vendor_entries) == 1
        assert vendor_entries[0].priority == 10  # first one wins

    def test_rejects_no_remote_no_local(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "broken",
                    }
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        assert len(gc.repo_entries) == 1
        assert gc.repo_entries[0].id == "ruyisdk"

    def test_rejects_relative_local_path(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "bad-path",
                        "local": "relative/path",
                    }
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        assert len(gc.repo_entries) == 1

    def test_local_only_repo(
        self,
        tmp_path: "object",
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "local-only",
                        "local": "/tmp/some/repo",
                        "priority": 5,
                    }
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        entries = gc.repo_entries
        local_entry = [e for e in entries if e.id == "local-only"]
        assert len(local_entry) == 1
        assert local_entry[0].local_path == "/tmp/some/repo"
        assert local_entry[0].remote == ""
        assert local_entry[0].active is True

    def test_defaults_for_optional_fields(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "minimal",
                        "remote": "https://example.invalid/repo.git",
                    }
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        entry = [e for e in gc.repo_entries if e.id == "minimal"][0]
        assert entry.name == "minimal"  # defaults to id
        assert entry.branch == "main"
        assert entry.priority == 0
        assert entry.active is True
        assert entry.local_path is None

    def test_inactive_repo(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "repos": [
                    {
                        "id": "disabled",
                        "remote": "https://example.invalid/repo.git",
                        "active": False,
                    }
                ]
            },
            is_global_scope=False,
        )
        if "repo_entries" in gc.__dict__:
            del gc.__dict__["repo_entries"]

        entry = [e for e in gc.repo_entries if e.id == "disabled"][0]
        assert entry.active is False
