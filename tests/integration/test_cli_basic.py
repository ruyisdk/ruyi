import io
import json
import pathlib
import sys
from tests.fixtures import IntegrationTestHarness

import pytest

from ruyi.cli.main import is_version_query, main as ruyi_main
from ruyi.log import RuyiConsoleLogger
from ruyi.ruyipkg.distfile import Distfile
from ruyi.ruyipkg.host import get_native_host

SHA_STUB = "0" * 64


class _TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def _fail_on_repo_access(self: object) -> None:
    raise AssertionError("completion setup must not access the package repo")


def test_cli_version_query_detection() -> None:
    assert is_version_query(["ruyi", "--version"])
    assert is_version_query(["ruyi", "-V"])
    assert is_version_query(["ruyi", "--porcelain", "--version"])
    assert is_version_query(["ruyi", "--config", "foo", "--version"])
    assert is_version_query(["ruyi", "version"])
    assert is_version_query(["ruyi", "--porcelain", "version"])
    assert not is_version_query(["ruyi"])
    assert not is_version_query(["ruyi", "list"])
    assert not is_version_query(["ruyi", "list", "version"])


def test_cli_version(ruyi_cli_runner: IntegrationTestHarness) -> None:
    for argv in [
        ["--version"],
        ["version"],
    ]:
        result = ruyi_cli_runner(*argv)
        assert result.exit_code == 0
        assert "Ruyi" in result.stdout
        assert "fatal error" not in result.stderr.lower()


def test_output_completion_script_does_not_access_repo_or_telemetry(
    ruyi_cli_runner: IntegrationTestHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ruyi.ruyipkg.repo import MetadataRepo

    monkeypatch.setattr(MetadataRepo, "ensure_git_repo", _fail_on_repo_access)

    result = ruyi_cli_runner("--output-completion-script=bash")

    assert result.exit_code == 0
    assert result.stdout.startswith("#compdef ruyi\n")
    assert "__python_argcomplete_ruyi_run" in result.stdout
    assert "package repository" not in result.stderr

    telemetry_root = pathlib.Path(ruyi_cli_runner._env["XDG_STATE_HOME"]) / "ruyi"
    assert not (telemetry_root / "telemetry" / "installation.json").exists()
    assert not (telemetry_root / "telemetry" / "minimal-installation-marker").exists()


def test_autocomplete_parser_build_does_not_access_package_repo(
    ruyi_cli_runner: IntegrationTestHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ruyi.cli import builtin_commands
    from ruyi.cli.cmd import RootCommand
    from ruyi.ruyipkg.repo import MetadataRepo

    del builtin_commands

    ctx = ruyi_cli_runner.make_command_context()
    ctx.gm._is_cli_autocomplete = True  # pylint: disable=protected-access
    monkeypatch.setattr(MetadataRepo, "ensure_git_repo", _fail_on_repo_access)

    RootCommand.build_argparse(ctx.gc)


def test_cli_version_skips_first_run_oobe(
    ruyi_cli_runner: IntegrationTestHarness,
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    for argv in [
        ("--version",),
        ("version",),
    ]:
        ctx = ruyi_cli_runner.make_command_context(*argv)
        stdout = _TTYStringIO()
        stderr = _TTYStringIO()

        ctx.gc.logger = RuyiConsoleLogger(ctx.gm, stdout=stdout, stderr=stderr)
        monkeypatch.setattr(sys, "stdin", _TTYStringIO())
        monkeypatch.setattr(sys, "stdout", stdout)
        monkeypatch.setattr(sys, "stderr", stderr)

        exit_code = ruyi_main(ctx.gm, ctx.gc, ctx.argv)

        assert exit_code == 0
        assert "Ruyi" in stdout.getvalue()
        assert "Welcome to RuyiSDK" not in stderr.getvalue()

        telemetry_root = pathlib.Path(ctx.gc.telemetry_root)
        assert not (telemetry_root / "installation.json").exists()
        assert not (telemetry_root / "minimal-installation-marker").exists()


def test_cli_list_with_mock_repo(ruyi_cli_runner: IntegrationTestHarness) -> None:
    result = ruyi_cli_runner("list", "--name-contains", "sample-cli")

    assert result.exit_code == 0
    assert "dev-tools/sample-cli" in result.stdout


def test_cli_list_with_custom_package(ruyi_cli_runner: IntegrationTestHarness) -> None:
    manifest = (
        'format = "v1"\n'
        'kind = ["source"]\n\n'
        "[metadata]\n"
        'desc = "Custom integration package"\n'
        'vendor = { name = "Integration Tests", eula = "" }\n\n'
        "[[distfiles]]\n"
        'name = "custom-src.tar.zst"\n'
        "size = 0\n\n"
        "[distfiles.checksums]\n"
        f'sha256 = "{SHA_STUB}"\n'
    )
    ruyi_cli_runner.add_package("examples", "custom-cli", "0.1.0", manifest)

    result = ruyi_cli_runner("list", "--category-is", "examples")

    assert result.exit_code == 0
    assert "examples/custom-cli" in result.stdout


def test_cli_list_shows_current_host_download_size(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    native_host = str(get_native_host())
    manifest = f"""\
format = "v1"
kind = ["binary"]

[metadata]
desc = "Binary integration package"
vendor = {{ name = "Integration Tests", eula = "" }}

[[distfiles]]
name = "current-host.tar.zst"
size = 123

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[[distfiles]]
name = "other-host.tar.zst"
size = 456

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[[binary]]
host = "{native_host}"
distfiles = ["current-host.tar.zst"]

[[binary]]
host = "linux/not-current"
distfiles = ["other-host.tar.zst"]
"""
    ruyi_cli_runner.add_package("examples", "binary-size", "1.0.0", manifest)

    result = ruyi_cli_runner("list", "--name-contains", "binary-size")

    assert result.exit_code == 0
    assert "examples/binary-size" in result.stdout
    assert f"download: 123 B for {native_host}" in result.stdout
    assert "456 bytes" not in result.stdout


def test_cli_list_verbose_shows_current_host_download_size(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    native_host = str(get_native_host())
    manifest = f"""\
format = "v1"
kind = ["source"]

[metadata]
desc = "Source integration package"
vendor = {{ name = "Integration Tests", eula = "" }}

[[distfiles]]
name = "verbose-src.tar.zst"
size = 789

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[source]
distfiles = ["verbose-src.tar.zst"]
"""
    ruyi_cli_runner.add_package("examples", "verbose-size", "1.0.0", manifest)

    result = ruyi_cli_runner("list", "--name-contains", "verbose-size", "-v")

    assert result.exit_code == 0
    assert "examples/verbose-size" in result.stdout
    assert f"Download size for {native_host}: 789 B" in result.stdout


def test_cli_list_porcelain_reports_current_host_download_size(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    native_host = str(get_native_host())
    manifest = f"""\
format = "v1"
kind = ["binary"]

[metadata]
desc = "Binary integration package"
vendor = {{ name = "Integration Tests", eula = "" }}

[[distfiles]]
name = "current-host-a.tar.zst"
size = 100

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[[distfiles]]
name = "current-host-b.tar.zst"
size = 23

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[[distfiles]]
name = "other-host.tar.zst"
size = 456

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[[binary]]
host = "{native_host}"
distfiles = ["current-host-a.tar.zst", "current-host-b.tar.zst"]

[[binary]]
host = "linux/not-current"
distfiles = ["other-host.tar.zst"]
"""
    ruyi_cli_runner.add_package("examples", "porcelain-size", "1.0.0", manifest)

    result = ruyi_cli_runner(
        "--porcelain",
        "list",
        "--name-contains",
        "porcelain-size",
    )

    assert result.exit_code == 0
    obj = json.loads(result.stdout)
    ver = obj["vers"][0]
    assert obj["category"] == "examples"
    assert obj["name"] == "porcelain-size"
    assert ver["download_size_host_bytes"] == 123
    assert ver["download_size_host"] == native_host


def test_cli_extract_without_subdir_reports_current_directory(
    ruyi_cli_runner: IntegrationTestHarness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = f"""\
format = "v1"
kind = ["source"]

[metadata]
desc = "Extract message package"
vendor = {{ name = "Integration Tests", eula = "" }}

[[distfiles]]
name = "extract-src.raw"
size = 0
unpack = "raw"

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[source]
distfiles = ["extract-src.raw"]
"""
    ruyi_cli_runner.add_package("examples", "extract-message", "1.0.0", manifest)

    unpack_roots: list[object] = []

    def fake_ensure(self: object, logger: object) -> None:
        pass

    def fake_unpack(self: object, root: object, logger: object) -> None:
        unpack_roots.append(root)

    monkeypatch.setattr(Distfile, "ensure", fake_ensure)
    monkeypatch.setattr(Distfile, "unpack", fake_unpack)

    result = ruyi_cli_runner(
        "extract",
        "--extract-without-subdir",
        "examples/extract-message",
    )

    assert result.exit_code == 0
    assert unpack_roots == [None]
    assert "has been extracted to ." in result.stderr
    assert "has been extracted to None" not in result.stderr
