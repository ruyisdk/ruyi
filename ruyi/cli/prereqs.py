import shutil
import sys

from ruyi import log


def ensure_git_binary() -> None:
    try:
        import git
    except ImportError:
        log.F(
            "seems [yellow]git[/yellow] is not available, which [yellow]ruyi[/yellow] requires"
        )
        log.I("please install Git and retry")
        sys.exit(1)


def has_cmd_in_path(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def check_nonessential_binaries() -> None:
    absent_cmds = [
        cmd
        for cmd in ("tar", "gunzip", "bzip2", "xz", "zstd")
        if not has_cmd_in_path(cmd)
    ]
    if not absent_cmds:
        return

    cmds_str = log.humanize_list(absent_cmds, item_color="yellow")
    log.W(f"The command(s) {cmds_str} cannot be found in PATH")
    log.I(
        "some features of [yellow]ruyi[/yellow] may depend on those commands; please install them and retry if anything fails due to this"
    )


def check_dep_binaries() -> None:
    ensure_git_binary()
    check_nonessential_binaries()
