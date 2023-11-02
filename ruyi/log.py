from typing import Any, IO, Optional
import sys

from rich.console import Console

from . import is_debug


DEBUG_CONSOLE = Console(file=sys.stderr)
LOG_CONSOLE = Console(file=sys.stderr, highlight=False)


def D(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
) -> None:
    if not is_debug():
        return

    return DEBUG_CONSOLE.print(
        f"[cyan]debug:[/cyan] {message}",
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
