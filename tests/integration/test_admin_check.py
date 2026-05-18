from contextlib import redirect_stderr, redirect_stdout
import json
import pathlib

import pytest

from ruyi.cli.main import main as ruyi_main
from tests.fixtures import IntegrationTestHarness


SHA_STUB = "0" * 64


CANONICAL_MANIFEST = f"""format = "v1"

[metadata]
desc = "Test package"
vendor = {{ name = "Test Vendor", eula = "" }}

[[distfiles]]
name = "src.tar.zst"
size = 0

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[source]
distfiles = ["src.tar.zst"]
"""


NON_CANONICAL_MANIFEST = f"""format = "v1"

[[distfiles]]
size = 0
name = "src.tar.zst"

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[metadata]
vendor = {{ eula = "", name = "Test Vendor" }}
desc = "Test package"

[source]
distfiles = ["src.tar.zst"]
"""


def test_admin_check_file_exits_zero_for_good_manifest(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(CANONICAL_MANIFEST, encoding="utf-8")

    result = ruyi_cli_runner("admin", "check", "-f", str(manifest_path))

    assert result.exit_code == 0
    assert "0 error(s), 0 warning(s)" in result.stdout


def test_admin_check_accepts_multiple_file_flags(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    first_path = tmp_path / "1.0.0.toml"
    second_path = tmp_path / "2.0.0.toml"
    first_path.write_text(CANONICAL_MANIFEST, encoding="utf-8")
    second_path.write_text(CANONICAL_MANIFEST, encoding="utf-8")

    result = ruyi_cli_runner(
        "admin",
        "check",
        "-f",
        str(first_path),
        "--file",
        str(second_path),
    )

    assert result.exit_code == 0
    assert "0 error(s), 0 warning(s)" in result.stdout


def test_admin_check_file_reports_diagnostics(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(NON_CANONICAL_MANIFEST, encoding="utf-8")

    result = ruyi_cli_runner("admin", "check", "-f", str(manifest_path))

    assert result.exit_code == 1
    assert "RYC0001" in result.stdout
    assert str(manifest_path) in result.stdout


def test_admin_check_repo_exits_zero_for_default_fixture_repo(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    result = ruyi_cli_runner(
        "admin",
        "check",
        "--repo",
        str(ruyi_cli_runner.repo_root),
    )

    assert result.exit_code == 0
    assert "0 error(s), 0 warning(s)" in result.stdout


def test_admin_check_repo_reports_multiple_diagnostics(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    repo_root = ruyi_cli_runner.repo_root
    ruyi_cli_runner.add_package("source", "bad-toml", "1.0.0", 'format = "v1"\n[')
    ruyi_cli_runner.add_package(
        "source",
        "bad-version",
        "not-semver",
        CANONICAL_MANIFEST,
    )

    result = ruyi_cli_runner("admin", "check", "--repo", str(repo_root))

    assert result.exit_code == 1
    assert "RYC0002" in result.stdout
    assert "RYC0004" in result.stdout


def test_admin_check_file_and_repo_fail_argument_validation(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(CANONICAL_MANIFEST, encoding="utf-8")

    with pytest.raises(SystemExit):
        ruyi_cli_runner(
            "admin",
            "check",
            "-f",
            str(manifest_path),
            "--repo",
            str(ruyi_cli_runner.repo_root),
        )


def test_admin_check_help_is_registered(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    ctx = ruyi_cli_runner.make_command_context("admin", "check", "--help")

    with (
        pytest.raises(SystemExit) as exc_info,
        redirect_stdout(ctx.stdout),
        redirect_stderr(ctx.stderr),
    ):
        ruyi_main(ctx.gm, ctx.gc, ctx.argv)

    assert exc_info.value.code == 0
    assert "usage: ruyi admin check" in ctx.stdout.getvalue()
    assert "--repo" in ctx.stdout.getvalue()
    assert "--only-packages" in ctx.stdout.getvalue()


def test_admin_check_only_packages_uses_list_style_selectors(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    source_path = ruyi_cli_runner.add_package(
        "source",
        "ignored-source",
        "1.0.0",
        'format = "v1"\n[',
    )
    board_path = ruyi_cli_runner.add_package(
        "board-image",
        "selected-board",
        "1.0.0",
        NON_CANONICAL_MANIFEST,
    )

    result = ruyi_cli_runner(
        "admin",
        "check",
        "--repo",
        str(ruyi_cli_runner.repo_root),
        "--only-packages",
        "--category-is",
        "board-image",
    )

    assert result.exit_code == 1
    assert "RYC0001" in result.stdout
    assert str(board_path) in result.stdout
    assert str(source_path) not in result.stdout
    assert "RYC0002" not in result.stdout


def test_admin_check_porcelain_emits_jsonl_diagnostics(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(NON_CANONICAL_MANIFEST, encoding="utf-8")

    result = ruyi_cli_runner(
        "--porcelain",
        "admin",
        "check",
        "-f",
        str(manifest_path),
    )

    assert result.exit_code == 1
    entities = [json.loads(line) for line in result.stdout.splitlines()]
    assert [entity["ty"] for entity in entities] == ["checkdiagnostic-v1"]
    assert entities[0]["code"] == "RYC0001"
