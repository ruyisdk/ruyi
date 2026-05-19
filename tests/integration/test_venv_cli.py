import argparse
import os
import pathlib
import shutil

import pytest

from ruyi.cli.completion import ArgumentParser
from ruyi.mux.venv.maker import (
    SysrootProvisionMode,
    VenvProvisionError,
    provision_sysroot,
)
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
    assert args.project_sysroot_from_rootfs is None

    args = p.parse_args(
        [
            "default",
            "./venv",
            "--symlink-sysroot-from-dir",
            "/tmp/sysroot",
        ]
    )
    assert args.symlink_sysroot_from_dir == "/tmp/sysroot"

    args = p.parse_args(
        [
            "default",
            "./venv",
            "--project-sysroot-from-rootfs",
            "/tmp/rootfs",
        ]
    )
    assert args.project_sysroot_from_rootfs == "/tmp/rootfs"


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
        project_sysroot_from_rootfs=None,
        extra_commands_from=None,
    )

    rc = VenvCommand.main(ctx.gc, args)
    assert rc == 1
    assert ctx.fatal_messages == [
        "at most one of --copy-sysroot-from-pkg, --copy-sysroot-from-dir, --symlink-sysroot-from-dir, and --project-sysroot-from-rootfs may be specified"
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
        project_sysroot_from_rootfs=None,
        extra_commands_from=None,
    )

    rc = VenvCommand.main(ctx.gc, args)
    assert rc == 1
    assert ctx.fatal_messages == [
        "--without-sysroot cannot be combined with a sysroot source option"
    ]


def test_copy_sysroot_failure_reports_clean_diagnostic(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    ctx = ruyi_cli_runner.make_command_context("venv")
    src = tmp_path / "sysroot"
    dest = tmp_path / "venv" / "sysroot.riscv64-test-linux-gnu"
    src.mkdir()

    def fake_copytree(*args: object, **kwargs: object) -> None:
        raise shutil.Error(
            [
                (
                    str(src / "etc" / "shadow"),
                    str(dest / "etc" / "shadow"),
                    "permission denied",
                ),
            ]
        )

    monkeypatch.setattr(shutil, "copytree", fake_copytree)

    with pytest.raises(VenvProvisionError):
        provision_sysroot(
            ctx.gc.logger,
            src,
            dest,
            SysrootProvisionMode.COPY_TREE,
            "riscv64-test-linux-gnu",
        )

    assert ctx.fatal_messages == [
        f"cannot copy sysroot from {src}: one entry could not be copied"
    ]
    assert (
        "Ruyi does not elevate privileges when creating virtual environments"
        in ctx.stderr.getvalue()
    )


def test_project_sysroot_from_rootfs_copies_common_roots(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    ctx = ruyi_cli_runner.make_command_context("venv")
    src = tmp_path / "rootfs"
    dest = tmp_path / "venv" / "sysroot.riscv64-test-linux-gnu"

    (src / "usr" / "include").mkdir(parents=True)
    (src / "usr" / "include" / "game.h").write_text("#pragma once\n", encoding="utf-8")
    (src / "usr" / "lib").mkdir(parents=True)
    (src / "usr" / "lib" / "libgame.so").write_bytes(b"fake so")
    (src / "usr" / "lib" / "ld-linux-riscv64-lp64d.so.1").write_bytes(b"fake ld")
    (src / "lib64").mkdir()
    os.symlink(
        "/usr/lib/ld-linux-riscv64-lp64d.so.1",
        src / "lib64" / "ld-linux-riscv64-lp64d.so.1",
    )
    (src / "etc").mkdir()
    (src / "etc" / "shadow").write_text("should not be copied\n", encoding="utf-8")

    provision_sysroot(
        ctx.gc.logger,
        src,
        dest,
        SysrootProvisionMode.PROJECT_ROOTFS,
        "riscv64-test-linux-gnu",
    )

    assert (dest / "usr" / "include" / "game.h").read_text(
        encoding="utf-8"
    ) == "#pragma once\n"
    assert (dest / "usr" / "lib" / "libgame.so").read_bytes() == b"fake so"
    assert not (dest / "etc" / "shadow").exists()
    assert os.readlink(dest / "lib64" / "ld-linux-riscv64-lp64d.so.1") == (
        "../usr/lib/ld-linux-riscv64-lp64d.so.1"
    )


def test_project_sysroot_from_rootfs_skips_unsupported_entries(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    ctx = ruyi_cli_runner.make_command_context("venv")
    src = tmp_path / "rootfs"
    dest = tmp_path / "venv" / "sysroot.riscv64-test-linux-gnu"
    (src / "usr" / "lib").mkdir(parents=True)
    (src / "usr" / "lib" / "libgame.so").write_bytes(b"fake so")
    os.mkfifo(src / "usr" / "lib" / "unsupported-fifo")

    provision_sysroot(
        ctx.gc.logger,
        src,
        dest,
        SysrootProvisionMode.PROJECT_ROOTFS,
        "riscv64-test-linux-gnu",
    )

    assert (dest / "usr" / "lib" / "libgame.so").read_bytes() == b"fake so"
    assert not (dest / "usr" / "lib" / "unsupported-fifo").exists()
    assert "some unreadable or unsupported files were skipped" in ctx.stderr.getvalue()


def test_project_sysroot_from_rootfs_fails_without_supported_roots(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    ctx = ruyi_cli_runner.make_command_context("venv")
    src = tmp_path / "rootfs"
    dest = tmp_path / "venv" / "sysroot.riscv64-test-linux-gnu"
    (src / "etc").mkdir(parents=True)

    with pytest.raises(VenvProvisionError):
        provision_sysroot(
            ctx.gc.logger,
            src,
            dest,
            SysrootProvisionMode.PROJECT_ROOTFS,
            "riscv64-test-linux-gnu",
        )

    assert ctx.fatal_messages == [
        f"cannot project sysroot from {src}: no supported sysroot directories were found"
    ]
