import shutil
import sys
from typing import Final, Iterable, NoReturn

from ..cli.user_input import pause_before_continuing
from ..i18n import _
from ..log import RuyiLogger, humanize_list


def has_cmd_in_path(cmd: str) -> bool:
    return shutil.which(cmd) is not None


_UNPACK_CMDS: Final = (
    "tar",
    "unzip",
)

_PROVISION_CMDS: Final = (
    "sudo",
    "dd",
    "fastboot",
)

_CMDS = _UNPACK_CMDS + _PROVISION_CMDS

_CMD_PRESENCE_MAP: Final[dict[str, bool]] = {}


def _get_cmds_for_platform() -> tuple[str, ...]:
    if sys.platform == "darwin":
        return _UNPACK_CMDS
    return _CMDS


def init_cmd_presence_map() -> None:
    _CMD_PRESENCE_MAP.clear()
    for cmd in _get_cmds_for_platform():
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
        prompt = _(
            "The command(s) {cmds} cannot be found in PATH, which [yellow]ruyi[/] requires"
        ).format(cmds=cmds_str)
        if not interactive_retry:
            logger.F(prompt)
            logger.I(_("please install and retry"))
            sys.exit(1)

        logger.W(prompt)
        logger.I(
            _(
                "please install them and press [green]Enter[/] to retry, or [green]Ctrl+C[/] to exit"
            )
        )
        try:
            pause_before_continuing(logger)
        except EOFError:
            logger.I(_("exiting due to EOF"))
            sys.exit(1)
        except KeyboardInterrupt:
            logger.I(_("exiting due to keyboard interrupt"))
            sys.exit(1)
