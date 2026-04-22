import pathlib
from typing import TYPE_CHECKING

import pygit2

from ruyi.ruyipkg.composite_repo import CompositeRepo
from ruyi.ruyipkg.repo import RepoEntry

if TYPE_CHECKING:
    from tests.fixtures import MockGlobalModeProvider
    from ruyi.log import RuyiLogger


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


def _init_repo_dir(root: pathlib.Path) -> None:
    """Initialize a bare-minimum git repo at root for MetadataRepo."""
    root.mkdir(parents=True, exist_ok=True)
    pygit2.init_repository(str(root))


def _write_manifest(
    root: pathlib.Path,
    category: str,
    name: str,
    ver: str,
    *,
    slug: str | None = None,
    desc: str = "test package",
) -> None:
    """Write a minimal package manifest TOML file into a repo tree."""
    pkg_dir = root / "packages" / category / name
    pkg_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        'format = "v1"',
        'kind = ["source"]',
        "distfiles = []",
        "",
        "[metadata]",
        f'desc = "{desc}"',
    ]
    if slug is not None:
        lines.append(f'slug = "{slug}"')
    lines.extend(
        [
            "",
            "[metadata.vendor]",
            'name = "test-vendor"',
        ]
    )
    (pkg_dir / f"{ver}.toml").write_text("\n".join(lines) + "\n")


def _write_profile_plugin(
    root: pathlib.Path,
    arch: str,
    profile_ids: list[str],
    *,
    quirks_by_profile: dict[str, list[str]] | None = None,
) -> None:
    plugin_dir = root / "plugins" / f"ruyi-profile-{arch}"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    plugin_text = "\n".join(
        [
            "def list_all_profile_ids_v1():",
            f"    return {profile_ids!r}",
            "",
            "def list_needed_quirks_v1(profile_id):",
            f"    return {quirks_by_profile or {}!r}.get(profile_id, [])",
            "",
        ]
    )
    (plugin_dir / "mod.star").write_text(plugin_text, encoding="utf-8")


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


class TestCompositeRepoMultiEntryMerge:
    """Tests for multi-repo merge, deduplication, and priority shadowing."""

    def _make_composite(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> CompositeRepo:
        """Set up two repos with overlapping and unique packages.

        base (priority=0):
          toolchain/gcc 13.1.0 (slug=gcc-13)
          toolchain/gcc 13.2.0
          toolchain/llvm 17.0.0

        overlay (priority=100):
          toolchain/gcc 13.2.0 (shadows base, different desc)
          toolchain/gcc 14.0.0 (unique to overlay)
          source/some-lib 1.0.0 (unique category)
        """
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)

        base_root = tmp_path / "base"
        _init_repo_dir(base_root)
        _write_manifest(base_root, "toolchain", "gcc", "13.1.0", slug="gcc-13")
        _write_manifest(base_root, "toolchain", "gcc", "13.2.0", desc="base gcc 13.2")
        _write_manifest(base_root, "toolchain", "llvm", "17.0.0")

        overlay_root = tmp_path / "overlay"
        _init_repo_dir(overlay_root)
        _write_manifest(
            overlay_root, "toolchain", "gcc", "13.2.0", desc="overlay gcc 13.2"
        )
        _write_manifest(overlay_root, "toolchain", "gcc", "14.0.0")
        _write_manifest(overlay_root, "source", "some-lib", "1.0.0", slug="some-lib")

        base_entry = _make_entry(repo_id="base", priority=0, local_path=str(base_root))
        overlay_entry = _make_entry(
            repo_id="overlay", priority=100, local_path=str(overlay_root)
        )

        return CompositeRepo([overlay_entry, base_entry], gc)

    def test_iter_pkgs_merges_versions(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)
        pkgs = {(cat, name): vers for cat, name, vers in composite.iter_pkgs()}

        # gcc should have 3 versions merged
        assert ("toolchain", "gcc") in pkgs
        gcc_vers = pkgs[("toolchain", "gcc")]
        assert set(gcc_vers.keys()) == {"13.1.0", "13.2.0", "14.0.0"}

        # llvm from base only
        assert ("toolchain", "llvm") in pkgs
        assert set(pkgs[("toolchain", "llvm")].keys()) == {"17.0.0"}

        # some-lib from overlay only
        assert ("source", "some-lib") in pkgs

    def test_priority_shadowing_same_version(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        """When base and overlay both have gcc 13.2.0, overlay wins."""
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        pm = composite.get_pkg("gcc", "toolchain", "13.2.0")
        assert pm is not None
        # The overlay version should shadow the base.
        assert pm.repo_id == "overlay"
        assert pm.desc == "overlay gcc 13.2"

    def test_get_pkg_from_base_only(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        pm = composite.get_pkg("gcc", "toolchain", "13.1.0")
        assert pm is not None
        assert pm.repo_id == "base"

    def test_get_pkg_nonexistent(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)
        assert composite.get_pkg("nonexistent", "toolchain", "1.0.0") is None

    def test_get_pkg_latest_ver(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        latest = composite.get_pkg_latest_ver("gcc", "toolchain")
        assert latest.ver == "14.0.0"
        assert latest.repo_id == "overlay"

    def test_get_pkg_latest_ver_across_repos(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        """get_pkg_latest_ver without category uses merged by-name index."""
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        latest = composite.get_pkg_latest_ver("gcc")
        assert latest.ver == "14.0.0"

    def test_get_pkg_by_slug(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        # Slug from base repo
        pm = composite.get_pkg_by_slug("gcc-13")
        assert pm is not None
        assert pm.name == "gcc"

        # Slug from overlay repo
        pm = composite.get_pkg_by_slug("some-lib")
        assert pm is not None
        assert pm.name == "some-lib"

        assert composite.get_pkg_by_slug("nonexistent") is None

    def test_iter_pkg_vers_by_category(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        vers = list(composite.iter_pkg_vers("gcc", "toolchain"))
        ver_strs = {pm.ver for pm in vers}
        assert ver_strs == {"13.1.0", "13.2.0", "14.0.0"}

    def test_iter_pkg_vers_by_name_only(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        vers = list(composite.iter_pkg_vers("llvm"))
        assert len(vers) == 1
        assert vers[0].ver == "17.0.0"

    def test_iter_pkg_manifests_deduplicates(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        """iter_pkg_manifests should yield deduplicated manifests."""
        composite = self._make_composite(tmp_path, mock_gm, ruyi_logger)

        manifests = list(composite.iter_pkg_manifests())
        # Total unique (category, name, ver) tuples:
        # gcc: 13.1.0, 13.2.0, 14.0.0 = 3
        # llvm: 17.0.0 = 1
        # some-lib: 1.0.0 = 1
        # Total = 5
        keys = [(pm.category, pm.name, pm.ver) for pm in manifests]
        assert len(keys) == 5
        assert len(set(keys)) == 5  # all unique

    def test_slug_shadowing(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        """When two repos define the same slug, higher priority wins."""
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)

        base_root = tmp_path / "slug-base"
        _init_repo_dir(base_root)
        _write_manifest(
            base_root,
            "toolchain",
            "pkg-a",
            "1.0.0",
            slug="shared-slug",
            desc="from base",
        )

        overlay_root = tmp_path / "slug-overlay"
        _init_repo_dir(overlay_root)
        _write_manifest(
            overlay_root,
            "toolchain",
            "pkg-b",
            "2.0.0",
            slug="shared-slug",
            desc="from overlay",
        )

        base_entry = _make_entry(repo_id="base", priority=0, local_path=str(base_root))
        overlay_entry = _make_entry(
            repo_id="overlay", priority=100, local_path=str(overlay_root)
        )
        composite = CompositeRepo([base_entry, overlay_entry], gc)

        pm = composite.get_pkg_by_slug("shared-slug")
        assert pm is not None
        assert pm.desc == "from overlay"
        assert pm.repo_id == "overlay"

    def test_profile_queries_skip_broken_repo(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)

        base_root = tmp_path / "profile-base"
        _init_repo_dir(base_root)
        _write_profile_plugin(
            base_root,
            "riscv64",
            ["milkv-duo"],
            quirks_by_profile={"milkv-duo": ["xthead"]},
        )

        broken_root = tmp_path / "profile-broken"
        _init_repo_dir(broken_root)
        (broken_root / "plugins" / "ruyi-profile-riscv64").mkdir(
            parents=True,
            exist_ok=True,
        )

        base_entry = _make_entry(repo_id="base", priority=0, local_path=str(base_root))
        broken_entry = _make_entry(
            repo_id="broken",
            priority=100,
            local_path=str(broken_root),
        )
        composite = CompositeRepo([broken_entry, base_entry], gc)

        assert composite.get_supported_arches() == ["riscv64"]

        profiles = list(composite.iter_profiles_for_arch("riscv64"))
        assert [p.id for p in profiles] == ["milkv-duo"]
        assert profiles[0].need_quirks == {"xthead"}

        profile = composite.get_profile("milkv-duo")
        assert profile is not None
        assert profile.id == "milkv-duo"

        arch_profile = composite.get_profile_for_arch("riscv64", "milkv-duo")
        assert arch_profile is not None
        assert arch_profile.id == "milkv-duo"

    def test_profile_plugin_first_valid_repo_wins_per_arch(
        self,
        tmp_path: pathlib.Path,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        from ruyi.config import GlobalConfig

        gc = GlobalConfig(mock_gm, ruyi_logger)

        low_root = tmp_path / "profile-low"
        _init_repo_dir(low_root)
        _write_profile_plugin(
            low_root,
            "riscv64",
            ["low-profile"],
        )

        high_root = tmp_path / "profile-high"
        _init_repo_dir(high_root)
        _write_profile_plugin(
            high_root,
            "riscv64",
            ["high-profile"],
            quirks_by_profile={"high-profile": ["xthead"]},
        )

        low_entry = _make_entry(repo_id="low", priority=0, local_path=str(low_root))
        high_entry = _make_entry(
            repo_id="high",
            priority=100,
            local_path=str(high_root),
        )
        composite = CompositeRepo([high_entry, low_entry], gc)

        assert composite.get_supported_arches() == ["riscv64"]

        profiles = list(composite.iter_profiles_for_arch("riscv64"))
        assert [p.id for p in profiles] == ["high-profile"]
        assert profiles[0].need_quirks == {"xthead"}

        profile = composite.get_profile("high-profile")
        assert profile is not None
        assert profile.id == "high-profile"

        assert composite.get_profile("low-profile") is None
        assert composite.get_profile_for_arch("riscv64", "low-profile") is None
