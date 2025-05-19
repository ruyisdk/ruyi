import shutil
import sys
from typing import Final, NoReturn

from ..log import RuyiLogger, humanize_list


def has_cmd_in_path(cmd: str) -> bool:
    return shutil.which(cmd) is not None


_CMDS: Final = (
    "bzip2",
    "gunzip",
    "lz4",
    "tar",
    "xz",
    "zstd",
    "unzip",
    # commands used by the device provisioner
    "sudo",
    "dd",
    "fastboot",
)

_CMD_PRESENCE_MAP: Final[dict[str, bool]] = {}


def init_cmd_presence_map() -> None:
    for cmd in _CMDS:
        _CMD_PRESENCE_MAP[cmd] = has_cmd_in_path(cmd)


def ensure_cmds(logger: RuyiLogger, *cmds: str) -> None | NoReturn:
    if not _CMD_PRESENCE_MAP:
        init_cmd_presence_map()

    # in case any command's availability is not cached in advance
    for cmd in cmds:
        if cmd not in _CMD_PRESENCE_MAP:
            _CMD_PRESENCE_MAP[cmd] = has_cmd_in_path(cmd)

    absent_cmds = sorted(cmd for cmd in cmds if not _CMD_PRESENCE_MAP.get(cmd, False))
    if not absent_cmds:
        return None

    cmds_str = humanize_list(absent_cmds, item_color="yellow")
    logger.F(
        f"The command(s) {cmds_str} cannot be found in PATH, which [yellow]ruyi[/yellow] requires"
    )
    logger.I("please install and retry")
    sys.exit(1)
