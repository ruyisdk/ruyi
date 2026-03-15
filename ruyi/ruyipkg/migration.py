import os
import pathlib
import shutil
from typing import TYPE_CHECKING

from ..i18n import _

if TYPE_CHECKING:
    from ..log import RuyiLogger


def migrate_repo_dir(cache_root: str, logger: "RuyiLogger") -> None:
    """Migrate the legacy packages-index/ directory to repos/ruyisdk/.

    If ``<cache>/packages-index/`` exists (not as a symlink) and
    ``<cache>/repos/ruyisdk/`` does not, move the former to the latter
    and create a compatibility symlink at the old location.

    If both exist, or the old path is already a symlink, do nothing.
    """

    legacy_path = pathlib.Path(cache_root) / "packages-index"
    new_path = pathlib.Path(cache_root) / "repos" / "ruyisdk"

    # Nothing to migrate if the legacy directory doesn't exist or is
    # already a symlink (i.e. a previous migration already ran).
    if not legacy_path.exists() or legacy_path.is_symlink():
        return

    # Already migrated (both exist) — do nothing.
    if new_path.exists():
        return

    logger.I(
        _(
            "migrating repo directory from [yellow]{old}[/] to [yellow]{new}[/]"
        ).format(old=legacy_path, new=new_path)
    )

    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_path), str(new_path))

    # Create a compatibility symlink so that any code still using the old
    # path continues to work during the transition.
    os.symlink(str(new_path), str(legacy_path))

    logger.I(_("repo directory migration complete"))
