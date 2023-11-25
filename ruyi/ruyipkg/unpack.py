import re
import subprocess

from .. import log

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
