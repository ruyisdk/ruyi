import abc
import datetime
from functools import cached_property
import io
import sys
import time
from typing import Any, TextIO, TYPE_CHECKING

if TYPE_CHECKING:
    # too heavy at package import time
    from rich.console import Console, RenderableType
    from rich.text import Text

from ..utils.global_mode import ProvidesGlobalMode
from ..utils.porcelain import PorcelainEntity, PorcelainEntityType, PorcelainOutput


class PorcelainLog(PorcelainEntity):
    t: int
    """Timestamp of the message line in microseconds"""

    lvl: str
    """Log level of the message line (one of D, F, I, W)"""

    msg: str
    """Message content"""


def log_time_formatter(x: datetime.datetime) -> "Text":
    from rich.text import Text

    return Text(f"debug: [{x.isoformat()}]")


def _make_porcelain_log(
    t: int,
    lvl: str,
    message: "RenderableType",
    sep: str,
    *objects: Any,
) -> PorcelainLog:
    from rich.console import Console

    with io.StringIO() as buf:
        tmp_console = Console(file=buf)
        tmp_console.print(message, *objects, sep=sep, end="")
        return {
            "ty": PorcelainEntityType.LogV1,
            "t": t,
            "lvl": lvl,
            "msg": buf.getvalue(),
        }


class RuyiLogger(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        pass

    @property
    @abc.abstractmethod
    def log_console(self) -> "Console":
        raise NotImplementedError

    @abc.abstractmethod
    def stdout(
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def D(
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        _stack_offset_delta: int = 0,
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def F(
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def I(  # noqa: E743 # the name intentionally mimics Android logging for brevity
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def W(
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        raise NotImplementedError


class RuyiConsoleLogger(RuyiLogger):
    def __init__(
        self,
        gm: ProvidesGlobalMode,
        stdout: TextIO = sys.stdout,
        stderr: TextIO = sys.stderr,
    ) -> None:
        super().__init__()

        self._gm = gm
        self._stdout = stdout
        self._stderr = stderr

    @cached_property
    def _stdout_console(self) -> "Console":
        from rich.console import Console

        return Console(
            file=self._stdout,
            highlight=False,
            soft_wrap=True,
        )

    @cached_property
    def _debug_console(self) -> "Console":
        from rich.console import Console

        return Console(
            file=self._stderr,
            log_time_format=log_time_formatter,
            soft_wrap=True,
        )

    @cached_property
    def _log_console(self) -> "Console":
        from rich.console import Console

        return Console(
            file=self._stderr,
            highlight=False,
            soft_wrap=True,
        )

    @cached_property
    def _porcelain_sink(self) -> PorcelainOutput:
        return PorcelainOutput(self._stderr.buffer)

    @property
    def log_console(self) -> "Console":
        return self._log_console

    def _emit_porcelain_log(
        self,
        lvl: str,
        message: "RenderableType",
        sep: str = " ",
        *objects: Any,
    ) -> None:
        t = int(time.time() * 1000000)
        obj = _make_porcelain_log(t, lvl, message, sep, *objects)
        self._porcelain_sink.emit(obj)

    def stdout(
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        return self._stdout_console.print(message, *objects, sep=sep, end=end)

    def D(
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
        _stack_offset_delta: int = 0,
    ) -> None:
        if not self._gm.is_debug:
            return

        if self._gm.is_porcelain:
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
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        if self._gm.is_porcelain:
            return self._emit_porcelain_log("F", message, sep, *objects)

        return self.log_console.print(
            f"[bold red]fatal error:[/] {message}",
            *objects,
            sep=sep,
            end=end,
        )

    def I(  # noqa: E743 # the name intentionally mimics Android logging for brevity
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        if self._gm.is_porcelain:
            return self._emit_porcelain_log("I", message, sep, *objects)

        return self.log_console.print(
            f"[bold green]info:[/] {message}",
            *objects,
            sep=sep,
            end=end,
        )

    def W(
        self,
        message: "RenderableType",
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        if self._gm.is_porcelain:
            return self._emit_porcelain_log("W", message, sep, *objects)

        return self.log_console.print(
            f"[bold yellow]warn:[/] {message}",
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
    return sep.join(f"[{item_color}]{x}[/]" for x in obj)
