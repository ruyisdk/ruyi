import shutil
import sys
from typing import Final, Iterable, NoReturn

from ..cli.user_input import pause_before_continuing
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
    _CMD_PRESENCE_MAP.clear()
    for cmd in _CMDS:
        _CMD_PRESENCE_MAP[cmd] = has_cmd_in_path(cmd)


def ensure_cmds(
    logger: RuyiLogger,
    cmds: Iterable[str],
    interactive_retry: bool = True,
) -> None | NoReturn:
    # only allow interactive retry if stdin is a TTY
    interactive_retry = interactive_retry and sys.stdin.isatty()

    while True:
        if not _CMD_PRESENCE_MAP or interactive_retry:
            init_cmd_presence_map()

        # in case any command's availability is not cached in advance
        for cmd in cmds:
            if cmd not in _CMD_PRESENCE_MAP:
                _CMD_PRESENCE_MAP[cmd] = has_cmd_in_path(cmd)

        absent_cmds = sorted(
            cmd for cmd in cmds if not _CMD_PRESENCE_MAP.get(cmd, False)
        )
        if not absent_cmds:
            return None

        cmds_str = humanize_list(absent_cmds, item_color="yellow")
        prompt = f"The command(s) {cmds_str} cannot be found in PATH, which [yellow]ruyi[/] requires"
        if not interactive_retry:
            logger.F(prompt)
            logger.I("please install and retry")
            sys.exit(1)

        logger.W(prompt)
        logger.I(
            "please install them and press [green]Enter[/] to retry, or [green]Ctrl+C[/] to exit"
        )
        try:
            pause_before_continuing(logger)
        except EOFError:
            logger.I("exiting due to EOF")
            sys.exit(1)
        except KeyboardInterrupt:
            logger.I("exiting due to keyboard interrupt")
            sys.exit(1)
