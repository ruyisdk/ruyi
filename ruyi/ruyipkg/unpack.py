import os
import re
import subprocess
from typing import NoReturn

from .. import log
from ..cli import prereqs

RE_TARBALL = re.compile(r"\.tar(?:\.gz|\.bz2|\.xz|\.zst)?$")
RE_ZIP = re.compile(r"\.zip$")


class UnrecognizedPackFormatError(Exception):
    def __init__(self, filename: str) -> None:
        self.filename = filename

    def __str__(self) -> str:
        return f"don't know how to unpack file {self.filename}"


def do_unpack(
    filename: str,
    dest: str | None,
    strip_components: int,
) -> None:
    if RE_TARBALL.search(filename):
        return do_unpack_tar(filename, dest, strip_components)
    if RE_ZIP.search(filename):
        # TODO: handle strip_components somehow; the unzip(1) command currently
        # does not have such support.
        return do_unpack_zip(filename, dest)
    raise UnrecognizedPackFormatError(filename)


def do_unpack_or_symlink(
    filename: str,
    dest: str | None,
    strip_components: int,
) -> None:
    try:
        return do_unpack(filename, dest, strip_components)
    except UnrecognizedPackFormatError:
        # just symlink into destination
        return do_symlink(filename, dest)


def do_symlink(
    src_path: str,
    destdir: str | None,
) -> None:
    src_filename = os.path.basename(src_path)
    if destdir is None:
        # symlink into CWD
        dest = src_filename
    else:
        dest = os.path.join(destdir, src_filename)

    # avoid the hassle and pitfalls around relative paths and symlinks, and
    # just point to the target using absolute path
    symlink_target = os.path.abspath(src_path)
    os.symlink(symlink_target, dest)


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


def do_unpack_zip(
    filename: str,
    dest: str | None,
) -> None:
    argv = ["unzip", filename]
    if dest is not None:
        argv.extend(("-d", dest))
    log.D(f"about to call unzip: argv={argv}")
    retcode = subprocess.call(argv, cwd=dest)
    if retcode != 0:
        raise RuntimeError(f"unzip failed: command {' '.join(argv)} returned {retcode}")


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
    elif dest_filename.endswith(".zip"):
        required_cmds.append("unzip")

    if not required_cmds:
        return

    return prereqs.ensure_cmds(*required_cmds)
