import datetime
from typing import Any, IO, Iterable, Optional
import sys

from rich.console import Console
from rich.text import Text

from . import is_debug


def log_time_formatter(x: datetime.datetime) -> Text:
    return Text(f"debug: [{x.isoformat()}]")


STDOUT_CONSOLE = Console(file=sys.stdout, highlight=False)
DEBUG_CONSOLE = Console(file=sys.stderr, log_time_format=log_time_formatter)
LOG_CONSOLE = Console(file=sys.stderr, highlight=False)


def stdout(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    return STDOUT_CONSOLE.print(message, *objects, sep=sep, end=end)


def D(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    if not is_debug():
        return

    return DEBUG_CONSOLE.log(
        message,
        *objects,
        sep=sep,
        end=end,
    )


def F(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    return LOG_CONSOLE.print(
        f"[bold red]fatal error:[/bold red] {message}",
        *objects,
        sep=sep,
        end=end,
    )


def I(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
    file: Optional[IO[str]] = None,
    flush: bool = False,
) -> None:
    return LOG_CONSOLE.print(
        f"[bold green]info:[/bold green] {message}",
        *objects,
        sep=sep,
        end=end,
    )


def W(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    return LOG_CONSOLE.print(
        f"[bold yellow]warn:[/bold yellow] {message}",
        *objects,
        sep=sep,
        end=end,
    )


def humanize_list(
    l: list[str] | set[str],
    *,
    sep: str = ", ",
    item_color: str | None = None,
    empty_prompt: str = "(none)",
) -> str:
    if not l:
        return empty_prompt
    if item_color is None:
        return sep.join(l)
    return sep.join(f"[{item_color}]{x}[/{item_color}]" for x in l)
