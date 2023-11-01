import argparse
import pathlib

from .. import log
from .venv_maker import VenvMaker


def cli_venv(args: argparse.Namespace) -> int:
    dest = pathlib.Path(args.dest)
    override_name: str | None = args.name

    if override_name is not None:
        log.I(
            f"Creating a Ruyi virtual environment [cyan]'{override_name}'[/cyan] at [green]{dest}[/green]..."
        )
    else:
        log.I(f"Creating a Ruyi virtual environment at [green]{dest}[/green]...")

    maker = VenvMaker(dest.resolve(), override_name)
    maker.provision()

    log.I(
        """\
The virtual environment is now created.

You may activate it by sourcing the appropriate activation script in the
[green]bin[/green] directory, and deactivate by invoking `ruyi-deactivate`.
"""
    )

    return 0
