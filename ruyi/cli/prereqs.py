import sys

from ruyi import log


def ensure_git_binary() -> None:
    try:
        import git
    except ImportError:
        log.F(
            "seems [yellow]git[/yellow] is not available, which [yellow]ruyi[/yellow] requires"
        )
        log.I("please install Git and retry")
        sys.exit(1)
