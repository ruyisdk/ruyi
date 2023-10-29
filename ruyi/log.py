from typing import Any, IO, Optional
import sys

from rich import print

from . import is_debug


def D(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
    file: Optional[IO[str]] = None,
    flush: bool = False,
) -> None:
    if not is_debug():
        return

    return print(
        f"[cyan]debug:[/cyan] {message}",
        *objects,
        sep=sep,
        end=end,
        file=file or sys.stderr,
        flush=flush,
    )


def F(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
    file: Optional[IO[str]] = None,
    flush: bool = False,
) -> None:
    return print(
        f"[bold red]fatal error:[/bold red] {message}",
        *objects,
        sep=sep,
        end=end,
        file=file or sys.stderr,
        flush=flush,
    )


def I(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
    file: Optional[IO[str]] = None,
    flush: bool = False,
) -> None:
    return print(
        f"[bold green]info:[/bold green] {message}",
        *objects,
        sep=sep,
        end=end,
        file=file or sys.stderr,
        flush=flush,
    )


def W(
    message,
    *objects: Any,
    sep: str = " ",
    end: str = "\n",
    file: Optional[IO[str]] = None,
    flush: bool = False,
) -> None:
    return print(
        f"[bold yellow]warn:[/bold yellow] {message}",
        *objects,
        sep=sep,
        end=end,
        file=file or sys.stderr,
        flush=flush,
    )
