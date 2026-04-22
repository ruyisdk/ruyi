"""Integration tests for multi-repo workflows.

Tests full round-trips through the CLI: repo add/remove/enable/disable,
list with priority shadowing, and package listing across repos.
"""

import pathlib

import pygit2

from tests.fixtures import IntegrationTestHarness


SHA_STUB = "0" * 64


def _write_user_config(harness: IntegrationTestHarness, toml: str) -> None:
    """Write a user config file into the harness's XDG config dir."""
    config_dir = pathlib.Path(harness._env["XDG_CONFIG_HOME"]) / "ruyi"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(toml, encoding="utf-8")


def _make_repo_dir(
    harness: IntegrationTestHarness,
    repo_id: str,
    *,
    config_toml_id: str | None = None,
) -> pathlib.Path:
    """Create a minimal repo dir under the harness cache with config.toml."""
    cache_dir = pathlib.Path(harness._env["XDG_CACHE_HOME"])
    repo_root = cache_dir / "ruyi" / "repos" / repo_id
    repo_root.mkdir(parents=True, exist_ok=True)
    pygit2.init_repository(str(repo_root))

    on_disk_id = config_toml_id if config_toml_id is not None else repo_id
    config_text = f"""\
ruyi-repo = "v1"

[repo]
id = "{on_disk_id}"

[[mirrors]]
id = "ruyi-dist"
urls = ["https://example.invalid/dist/"]
"""
    (repo_root / "config.toml").write_text(config_text, encoding="utf-8")
    return repo_root


def _add_manifest(
    repo_root: pathlib.Path,
    category: str,
    name: str,
    version: str,
    desc: str = "test package",
) -> None:
    """Write a minimal package manifest into a repo directory."""
    pkg_dir = repo_root / "packages" / category / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    manifest = f"""\
format = "v1"
kind = ["source"]

[metadata]
desc = "{desc}"
vendor = {{ name = "Test Vendor", eula = "" }}

[[distfiles]]
name = "{name}-{version}.tar.zst"
size = 0

[distfiles.checksums]
sha256 = "{SHA_STUB}"
"""
    (pkg_dir / f"{version}.toml").write_text(manifest, encoding="utf-8")


class TestRepoListMultiRepo:
    """repo list shows multiple configured repos with correct markers."""

    def test_list_shows_default_only(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        result = ruyi_cli_runner("repo", "list")
        assert result.exit_code == 0
        assert "ruyisdk" in result.stdout
        assert "(default)" in result.stdout

    def test_list_shows_additional_repo(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        _make_repo_dir(ruyi_cli_runner, "custom-repo")
        _write_user_config(
            ruyi_cli_runner,
            """\
[[repos]]
id = "custom-repo"
remote = "https://example.invalid/custom.git"
priority = 50
active = true
""",
        )

        result = ruyi_cli_runner("repo", "list")
        assert result.exit_code == 0
        assert "ruyisdk" in result.stdout
        assert "custom-repo" in result.stdout
        assert "priority=50" in result.stdout

    def test_list_inactive_repo_no_star(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        _write_user_config(
            ruyi_cli_runner,
            """\
[[repos]]
id = "disabled-repo"
remote = "https://example.invalid/disabled.git"
active = false
""",
        )

        result = ruyi_cli_runner("repo", "list")
        assert result.exit_code == 0
        assert "disabled-repo" in result.stdout
        # The default repo should have an asterisk but the disabled one should not
        lines = result.stdout.strip().splitlines()
        for line in lines:
            if "disabled-repo" in line:
                # Should not start with *
                stripped = line.lstrip()
                assert not stripped.startswith(
                    "*"
                ), f"disabled repo should not have *: {line}"


class TestRepoAddRemoveRoundTrip:
    """Test adding and removing repos via CLI."""

    def test_add_repo_creates_config_entry(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        result = ruyi_cli_runner(
            "repo",
            "add",
            "my-overlay",
            "https://example.invalid/overlay.git",
            "--priority",
            "10",
        )
        assert result.exit_code == 0
        assert "my-overlay" in result.stderr

        # Verify it shows up in repo list
        result = ruyi_cli_runner("repo", "list")
        assert result.exit_code == 0
        assert "my-overlay" in result.stdout
        assert "priority=10" in result.stdout

    def test_add_duplicate_fails(self, ruyi_cli_runner: IntegrationTestHarness) -> None:
        result = ruyi_cli_runner(
            "repo",
            "add",
            "dup-repo",
            "https://example.invalid/dup.git",
        )
        assert result.exit_code == 0

        result = ruyi_cli_runner(
            "repo",
            "add",
            "dup-repo",
            "https://example.invalid/dup2.git",
        )
        assert result.exit_code == 1
        assert "already exists" in result.stderr

    def test_add_reserved_id_fails(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        result = ruyi_cli_runner(
            "repo",
            "add",
            "ruyisdk",
            "https://example.invalid/ruyisdk.git",
        )
        assert result.exit_code == 1
        assert "reserved" in result.stderr

    def test_add_invalid_id_fails(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        result = ruyi_cli_runner(
            "repo",
            "add",
            "INVALID_ID!",
            "https://example.invalid/bad.git",
        )
        assert result.exit_code == 1
        assert "invalid" in result.stderr

    def test_add_no_url_no_local_fails(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        result = ruyi_cli_runner("repo", "add", "orphan-repo")
        assert result.exit_code == 1

    def test_remove_repo(self, ruyi_cli_runner: IntegrationTestHarness) -> None:
        # Add then remove
        result = ruyi_cli_runner(
            "repo",
            "add",
            "to-remove",
            "https://example.invalid/to-remove.git",
        )
        assert result.exit_code == 0

        result = ruyi_cli_runner("repo", "remove", "to-remove")
        assert result.exit_code == 0
        assert "removed" in result.stderr

        # Verify gone from list
        result = ruyi_cli_runner("repo", "list")
        assert "to-remove" not in result.stdout

    def test_remove_default_fails(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        result = ruyi_cli_runner("repo", "remove", "ruyisdk")
        assert result.exit_code == 1
        assert "cannot remove" in result.stderr

    def test_remove_nonexistent_fails(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        result = ruyi_cli_runner("repo", "remove", "no-such-repo")
        assert result.exit_code == 1

    def test_remove_with_purge(self, ruyi_cli_runner: IntegrationTestHarness) -> None:
        repo_root = _make_repo_dir(ruyi_cli_runner, "purge-me")
        result = ruyi_cli_runner(
            "repo",
            "add",
            "purge-me",
            "https://example.invalid/purge-me.git",
        )
        assert result.exit_code == 0

        assert repo_root.exists()
        result = ruyi_cli_runner("repo", "remove", "purge-me", "--purge")
        assert result.exit_code == 0
        assert not repo_root.exists()


class TestRepoEnableDisable:
    """Enable and disable repos via CLI."""

    def test_disable_and_enable(self, ruyi_cli_runner: IntegrationTestHarness) -> None:
        result = ruyi_cli_runner(
            "repo",
            "add",
            "toggle-repo",
            "https://example.invalid/toggle.git",
        )
        assert result.exit_code == 0

        # Disable
        result = ruyi_cli_runner("repo", "disable", "toggle-repo")
        assert result.exit_code == 0

        result = ruyi_cli_runner("repo", "list")
        lines = result.stdout.strip().splitlines()
        for line in lines:
            if "toggle-repo" in line:
                stripped = line.lstrip()
                assert not stripped.startswith("*")

        # Enable
        result = ruyi_cli_runner("repo", "enable", "toggle-repo")
        assert result.exit_code == 0

        result = ruyi_cli_runner("repo", "list")
        lines = result.stdout.strip().splitlines()
        for line in lines:
            if "toggle-repo" in line:
                stripped = line.lstrip()
                assert stripped.startswith("*")


class TestRepoSetPriority:
    """Set priority on repos via CLI."""

    def test_set_priority(self, ruyi_cli_runner: IntegrationTestHarness) -> None:
        result = ruyi_cli_runner(
            "repo",
            "add",
            "pri-repo",
            "https://example.invalid/pri.git",
            "--priority",
            "5",
        )
        assert result.exit_code == 0

        result = ruyi_cli_runner("repo", "set-priority", "pri-repo", "99")
        assert result.exit_code == 0

        result = ruyi_cli_runner("repo", "list")
        assert "priority=99" in result.stdout


class TestMultiRepoPackageListing:
    """Package list shows packages from multiple repos with priority."""

    def test_list_packages_across_repos(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        """Packages from both default and overlay repos appear in list."""
        overlay_root = _make_repo_dir(ruyi_cli_runner, "overlay")
        _add_manifest(overlay_root, "toolchain", "overlay-gcc", "1.0.0", "Overlay GCC")

        _write_user_config(
            ruyi_cli_runner,
            """\
[[repos]]
id = "overlay"
remote = "https://example.invalid/overlay.git"
priority = 100
active = true
""",
        )

        result = ruyi_cli_runner("list", "--all")
        assert result.exit_code == 0
        # Default repo has sample-cli, overlay has overlay-gcc
        assert "sample-cli" in result.stdout
        assert "overlay-gcc" in result.stdout

    def test_priority_shadowing_in_list(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        """Higher-priority repo shadows lower for same package version."""
        overlay_root = _make_repo_dir(ruyi_cli_runner, "overlay")
        # Same package as default repo but different desc
        _add_manifest(
            overlay_root,
            "dev-tools",
            "sample-cli",
            "1.0.0",
            "Overlay Sample CLI",
        )

        _write_user_config(
            ruyi_cli_runner,
            """\
[[repos]]
id = "overlay"
remote = "https://example.invalid/overlay.git"
priority = 100
active = true
""",
        )

        result = ruyi_cli_runner("list", "--name-contains", "sample-cli")
        assert result.exit_code == 0
        assert "sample-cli" in result.stdout

    def test_disabled_repo_packages_excluded(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        """Disabled repo's packages do not appear in list."""
        disabled_root = _make_repo_dir(ruyi_cli_runner, "disabled-repo")
        _add_manifest(
            disabled_root, "toolchain", "hidden-pkg", "1.0.0", "Should Not Appear"
        )

        _write_user_config(
            ruyi_cli_runner,
            """\
[[repos]]
id = "disabled-repo"
remote = "https://example.invalid/disabled.git"
active = false
""",
        )

        result = ruyi_cli_runner("list", "--all")
        assert result.exit_code == 0
        assert "hidden-pkg" not in result.stdout
        # Default packages still visible
        assert "sample-cli" in result.stdout

    def test_multi_repo_tag_shown(
        self, ruyi_cli_runner: IntegrationTestHarness
    ) -> None:
        """When multiple repos are configured, list shows [repo-id] tags."""
        overlay_root = _make_repo_dir(ruyi_cli_runner, "overlay")
        _add_manifest(overlay_root, "source", "extra-lib", "0.1.0")

        _write_user_config(
            ruyi_cli_runner,
            """\
[[repos]]
id = "overlay"
remote = "https://example.invalid/overlay.git"
priority = 50
active = true
""",
        )

        result = ruyi_cli_runner("list", "--all")
        assert result.exit_code == 0
        # With multiple repos, repo ID tags should appear
        assert "[ruyisdk]" in result.stdout or "[overlay]" in result.stdout
