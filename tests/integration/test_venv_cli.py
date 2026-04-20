import argparse

from ruyi.cli.completion import ArgumentParser
from ruyi.mux.venv.venv_cli import VenvCommand
from tests.fixtures import IntegrationTestHarness


def make_parser(ruyi_cli_runner: IntegrationTestHarness) -> ArgumentParser:
    ctx = ruyi_cli_runner.make_command_context("venv")
    p = ruyi_cli_runner.make_parser()
    VenvCommand.configure_args(ctx.gc, p)
    return p


def test_parse_new_sysroot_source_flags(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    p = make_parser(ruyi_cli_runner)

    args = p.parse_args(
        [
            "default",
            "./venv",
            "--copy-sysroot-from-dir",
            "/tmp/sysroot",
        ]
    )
    assert args.copy_sysroot_from_dir == "/tmp/sysroot"
    assert args.symlink_sysroot_from_dir is None
    assert args.copy_sysroot_from_pkg is None

    args = p.parse_args(
        [
            "default",
            "./venv",
            "--symlink-sysroot-from-dir",
            "/tmp/sysroot",
        ]
    )
    assert args.symlink_sysroot_from_dir == "/tmp/sysroot"


def test_old_sysroot_from_alias_still_parses(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    p = make_parser(ruyi_cli_runner)

    args = p.parse_args(
        [
            "default",
            "./venv",
            "--sysroot-from",
            "gnu-plct",
        ]
    )
    assert args.copy_sysroot_from_pkg == "gnu-plct"


def test_sysroot_source_options_are_mutually_exclusive_at_main(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    ctx = ruyi_cli_runner.make_command_context("venv")
    args = argparse.Namespace(
        profile="default",
        dest="./venv",
        with_sysroot=True,
        name=None,
        toolchain=["gnu-plct"],
        emulator=None,
        copy_sysroot_from_pkg="foo",
        copy_sysroot_from_dir="/tmp/sysroot",
        symlink_sysroot_from_dir=None,
        extra_commands_from=None,
    )

    rc = VenvCommand.main(ctx.gc, args)
    assert rc == 1
    assert ctx.fatal_messages == [
        "at most one of --copy-sysroot-from-pkg, --copy-sysroot-from-dir, and --symlink-sysroot-from-dir may be specified"
    ]


def test_without_sysroot_conflicts_with_explicit_source(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    ctx = ruyi_cli_runner.make_command_context("venv")
    args = argparse.Namespace(
        profile="default",
        dest="./venv",
        with_sysroot=False,
        name=None,
        toolchain=["gnu-plct"],
        emulator=None,
        copy_sysroot_from_pkg=None,
        copy_sysroot_from_dir="/tmp/sysroot",
        symlink_sysroot_from_dir=None,
        extra_commands_from=None,
    )

    rc = VenvCommand.main(ctx.gc, args)
    assert rc == 1
    assert ctx.fatal_messages == [
        "--without-sysroot cannot be combined with a sysroot source option"
    ]
