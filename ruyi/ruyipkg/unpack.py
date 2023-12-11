import os
import re
import subprocess
from typing import NoReturn

from .. import log
from ..cli import prereqs

RE_TARBALL = re.compile(r"\.tar(?:\.gz|\.bz2|\.xz|\.zst)?$")


def do_unpack(
    filename: str,
    dest: str | None,
    strip_components: int,
) -> None:
    if RE_TARBALL.search(filename):
        return do_unpack_tar(filename, dest, strip_components)
    raise RuntimeError(f"don't know how to unpack file {filename}")


def do_unpack_tar(
    filename: str,
    dest: str | None,
    strip_components: int,
) -> None:
    argv = ["tar", "-x"]
    argv.extend(("-f", filename, f"--strip-components={strip_components}"))
    if dest is not None:
        argv.extend(("-C", dest))
    log.D(f"about to call tar: argv={argv}")
    retcode = subprocess.call(argv, cwd=dest)
    if retcode != 0:
        raise RuntimeError(f"untar failed: command {' '.join(argv)} returned {retcode}")


def ensure_unpack_cmd_for_distfile(dest_filename: str) -> None | NoReturn:
    dest_filename = dest_filename.lower()
    dest_filename = os.path.basename(dest_filename)

    required_cmds: list[str] = []
    strip_one_ext = False
    if dest_filename.endswith(".gz"):
        required_cmds.append("gunzip")
        strip_one_ext = True
    elif dest_filename.endswith(".bz2"):
        required_cmds.append("bzip2")
        strip_one_ext = True
    elif dest_filename.endswith(".xz"):
        required_cmds.append("xz")
        strip_one_ext = True
    elif dest_filename.endswith(".zst"):
        required_cmds.append("zstd")
        strip_one_ext = True

    if strip_one_ext:
        dest_filename = dest_filename.rsplit(".", 1)[0]

    if dest_filename.endswith(".tar"):
        required_cmds.append("tar")

    if not required_cmds:
        return

    return prereqs.ensure_cmds(*required_cmds)
