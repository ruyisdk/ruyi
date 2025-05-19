import datetime
import io
import sys
import time
from typing import Any, TextIO

from rich.console import Console, ConsoleRenderable
from rich.text import Text

from .. import is_debug, is_porcelain
from ..utils.porcelain import PorcelainEntity, PorcelainEntityType, PorcelainOutput


class PorcelainLog(PorcelainEntity):
    t: int
    """Timestamp of the message line in microseconds"""

    lvl: str
    """Log level of the message line (one of D, F, I, W)"""

    msg: str
    """Message content"""


def log_time_formatter(x: datetime.datetime) -> Text:
    return Text(f"debug: [{x.isoformat()}]")


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


class RuyiLogger:
    def __init__(
        self,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
    ) -> None:
        self._stdout_console = Console(
            file=stdout,
            highlight=False,
            soft_wrap=True,
        )
        self._debug_console = Console(
            file=stderr,
            log_time_format=log_time_formatter,
            soft_wrap=True,
        )
        self._log_console = Console(
            file=stderr,
            highlight=False,
            soft_wrap=True,
        )
        self._porcelain_sink = PorcelainOutput(stderr.buffer)

    @property
    def log_console(self) -> Console:
        return self._log_console

    def _emit_porcelain_log(
        self,
        lvl: str,
        message: Renderable,
        sep: str = " ",
        *objects: Any,
    ) -> None:
        t = int(time.time() * 1000000)
        obj = _make_porcelain_log(t, lvl, message, sep, *objects)
        self._porcelain_sink.emit(obj)

    def stdout(
        self,
        message: Renderable,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        return self._stdout_console.print(message, *objects, sep=sep, end=end)

    def D(
        self,
        message: Renderable,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        _stack_offset_delta: int = 0,
    ) -> None:
        if not is_debug():
            return

        if is_porcelain():
            return self._emit_porcelain_log("D", message, sep, *objects)

        return self._debug_console.log(
            message,
            *objects,
            sep=sep,
            end=end,
            _stack_offset=2 + _stack_offset_delta,
        )

    def F(
        self,
        message: Renderable,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        if is_porcelain():
            return self._emit_porcelain_log("F", message, sep, *objects)

        return self._log_console.print(
            f"[bold red]fatal error:[/bold red] {message}",
            *objects,
            sep=sep,
            end=end,
        )

    def I(  # noqa: E743 # the name intentionally mimics Android logging for brevity
        self,
        message: Renderable,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        if is_porcelain():
            return self._emit_porcelain_log("I", message, sep, *objects)

        return self._log_console.print(
            f"[bold green]info:[/bold green] {message}",
            *objects,
            sep=sep,
            end=end,
        )

    def W(
        self,
        message: Renderable,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        if is_porcelain():
            return self._emit_porcelain_log("W", message, sep, *objects)

        return self._log_console.print(
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
