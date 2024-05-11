import datetime
import io
import time
from typing import Any, IO, Optional
import sys

from rich.console import Console, ConsoleRenderable
from rich.text import Text

from . import is_debug, is_porcelain
from .utils.porcelain import PorcelainEntity, PorcelainEntityType, PorcelainOutput


class PorcelainLog(PorcelainEntity):
    t: int
    """Timestamp of the message line in microseconds"""

    lvl: str
    """Log level of the message line (one of D, F, I, W)"""

    msg: str
    """Message content"""


def log_time_formatter(x: datetime.datetime) -> Text:
    return Text(f"debug: [{x.isoformat()}]")


STDOUT_CONSOLE = Console(file=sys.stdout, highlight=False)
DEBUG_CONSOLE = Console(file=sys.stderr, log_time_format=log_time_formatter)
LOG_CONSOLE = Console(file=sys.stderr, highlight=False)
PORCELAIN_SINK = PorcelainOutput(sys.stderr.buffer)

Renderable = str | ConsoleRenderable


def _make_porcelain_log(
    t: int,
    lvl: str,
    message: Renderable,
    sep: str,
    *objects: Any,
) -> PorcelainLog:
    with io.StringIO() as buf:
        tmp_console = Console(file=buf)
        tmp_console.print(message, *objects, sep=sep, end="")
        return {
            "ty": PorcelainEntityType.LogV1,
            "t": t,
            "lvl": lvl,
            "msg": buf.getvalue(),
        }


def _emit_porcelain_log(
    lvl: str,
    message: Renderable,
    sep: str = " ",
    *objects: Any,
) -> None:
    t = int(time.time() * 1000000)
    obj = _make_porcelain_log(t, lvl, message, sep, *objects)
    PORCELAIN_SINK.emit(obj)


def stdout(
    message: Renderable,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    return STDOUT_CONSOLE.print(message, *objects, sep=sep, end=end)


def D(
    message: Renderable,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    if not is_debug():
        return

    if is_porcelain():
        return _emit_porcelain_log("D", message, sep, *objects)

    return DEBUG_CONSOLE.log(
        message,
        *objects,
        sep=sep,
        end=end,
        _stack_offset=2,
    )


def F(
    message: Renderable,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    if is_porcelain():
        return _emit_porcelain_log("F", message, sep, *objects)

    return LOG_CONSOLE.print(
        f"[bold red]fatal error:[/bold red] {message}",
        *objects,
        sep=sep,
        end=end,
    )


def I(  # noqa: E743 # the name intentionally mimics Android logging for brevity
    message: Renderable,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
    file: Optional[IO[str]] = None,
    flush: bool = False,
) -> None:
    if is_porcelain():
        return _emit_porcelain_log("I", message, sep, *objects)

    return LOG_CONSOLE.print(
        f"[bold green]info:[/bold green] {message}",
        *objects,
        sep=sep,
        end=end,
    )


def W(
    message: Renderable,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    if is_porcelain():
        return _emit_porcelain_log("W", message, sep, *objects)

    return LOG_CONSOLE.print(
        f"[bold yellow]warn:[/bold yellow] {message}",
        *objects,
        sep=sep,
        end=end,
    )


def humanize_list(
    obj: list[str] | set[str],
    *,
    sep: str = ", ",
    item_color: str | None = None,
    empty_prompt: str = "(none)",
) -> str:
    if not obj:
        return empty_prompt
    if item_color is None:
        return sep.join(obj)
    return sep.join(f"[{item_color}]{x}[/{item_color}]" for x in obj)
