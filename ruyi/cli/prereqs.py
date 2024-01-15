import shutil
import sys
from typing import NoReturn

from ruyi import log


def ensure_git_binary() -> None | NoReturn:
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


_CMDS = (
    "bzip2",
    "gunzip",
    "tar",
    "xz",
    "zstd",
    "unzip",
    # commands used by the device provisioner
    "dd",
    "fastboot",
)

_CMD_PRESENCE_MAP: dict[str, bool] = {}


def init_cmd_presence_map() -> None:
    global _CMD_PRESENCE_MAP
    _CMD_PRESENCE_MAP = {cmd: has_cmd_in_path(cmd) for cmd in _CMDS}


def ensure_cmds(*cmds: str) -> None | NoReturn:
    if not _CMD_PRESENCE_MAP:
        init_cmd_presence_map()

    absent_cmds = sorted(cmd for cmd in cmds if not _CMD_PRESENCE_MAP.get(cmd, False))
    if not absent_cmds:
        return

    cmds_str = log.humanize_list(absent_cmds, item_color="yellow")
    log.F(
        f"The command(s) {cmds_str} cannot be found in PATH, which [yellow]ruyi[/yellow] requires"
    )
    log.I("please install and retry")
    sys.exit(1)


def check_dep_binaries() -> None:
    ensure_git_binary()
    # init_cmd_presence_map() is called on-demand, to avoid having to reach out
    # to FS at every `ruyi` invocation which can get expensive.
