import os
import pathlib
import shutil
import subprocess
import tempfile
from typing import NoReturn

from .. import log
from ..cli import prereqs
from .unpack_method import UnpackMethod, UnrecognizedPackFormatError


def do_unpack(
    filename: str,
    dest: str | None,
    strip_components: int,
    unpack_method: UnpackMethod,
) -> None:
    if dest is None:
        return _do_unpack_inner(filename, dest, strip_components, unpack_method)

    # dest is a directory, create a temp directory besides it
    dest_path = pathlib.Path(dest)
    dest_parent = dest_path.resolve().parent
    with tempfile.TemporaryDirectory(
        prefix=f".{dest_path.name}.tmp",
        dir=dest_parent,
    ) as tmpdir_path:
        _do_unpack_inner(filename, tmpdir_path, strip_components, unpack_method)
        os.replace(tmpdir_path, dest)


def _do_unpack_inner(
    filename: str,
    dest: str | None,
    strip_components: int,
    unpack_method: UnpackMethod,
) -> None:
    match unpack_method:
        case UnpackMethod.AUTO:
            raise ValueError("the auto unpack method must be resolved prior to use")
        case UnpackMethod.RAW:
            return do_copy_raw(filename, dest)
        case (
            UnpackMethod.TAR_AUTO
            | UnpackMethod.TAR
            | UnpackMethod.TAR_BZ2
            | UnpackMethod.TAR_GZ
            | UnpackMethod.TAR_XZ
            | UnpackMethod.TAR_ZST
        ):
            return do_unpack_tar(filename, dest, strip_components, unpack_method)
        case UnpackMethod.ZIP:
            # TODO: handle strip_components somehow; the unzip(1) command currently
            # does not have such support.
            return do_unpack_zip(filename, dest)
        case UnpackMethod.GZ:
            # bare gzip file
            return do_unpack_bare_gz(filename, dest)
        case UnpackMethod.BZ2:
            # bare bzip2 file
            return do_unpack_bare_bzip2(filename, dest)
        case UnpackMethod.XZ:
            # bare xz file
            return do_unpack_bare_xz(filename, dest)
        case UnpackMethod.ZST:
            # bare zstd file
            return do_unpack_bare_zstd(filename, dest)
        case _:
            raise UnrecognizedPackFormatError(filename)


def do_unpack_or_symlink(
    filename: str,
    dest: str | None,
    strip_components: int,
    unpack_method: UnpackMethod,
) -> None:
    try:
        return do_unpack(filename, dest, strip_components, unpack_method)
    except UnrecognizedPackFormatError:
        # just symlink into destination
        return do_symlink(filename, dest)


def do_copy_raw(
    src_path: str,
    destdir: str | None,
) -> None:
    src_filename = os.path.basename(src_path)
    if destdir is None:
        # symlink into CWD
        dest = src_filename
    else:
        dest = os.path.join(destdir, src_filename)

    shutil.copy(src_path, dest)


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
    unpack_method: UnpackMethod,
) -> None:
    argv = ["tar", "-x"]

    match unpack_method:
        case UnpackMethod.TAR | UnpackMethod.TAR_AUTO:
            pass
        case UnpackMethod.TAR_GZ:
            argv.append("-z")
        case UnpackMethod.TAR_BZ2:
            argv.append("-j")
        case UnpackMethod.TAR_XZ:
            argv.append("-J")
        case UnpackMethod.TAR_ZST:
            argv.append("--zstd")
        case _:
            raise ValueError(
                f"do_unpack_tar cannot handle non-tar unpack method {unpack_method}"
            )

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


def do_unpack_bare_gz(
    filename: str,
    destdir: str | None,
) -> None:
    # the suffix may not be ".gz" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["gunzip", "-c", filename]
    if destdir is not None:
        os.chdir(destdir)

    log.D(f"about to call gunzip: argv={argv}")
    with open(dest_filename, "wb") as out:
        retcode = subprocess.call(argv, stdout=out)
        if retcode != 0:
            raise RuntimeError(
                f"gunzip failed: command {' '.join(argv)} returned {retcode}"
            )


def do_unpack_bare_bzip2(
    filename: str,
    destdir: str | None,
) -> None:
    # the suffix may not be ".bz2" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["bzip2", "-dc", filename]
    if destdir is not None:
        os.chdir(destdir)

    log.D(f"about to call bzip2: argv={argv}")
    with open(dest_filename, "wb") as out:
        retcode = subprocess.call(argv, stdout=out)
        if retcode != 0:
            raise RuntimeError(
                f"bzip2 failed: command {' '.join(argv)} returned {retcode}"
            )


def do_unpack_bare_xz(
    filename: str,
    destdir: str | None,
) -> None:
    # the suffix may not be ".xz" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["xz", "-d", "-c", filename]
    if destdir is not None:
        os.chdir(destdir)

    log.D(f"about to call xz: argv={argv}")
    with open(dest_filename, "wb") as out:
        retcode = subprocess.call(argv, stdout=out)
        if retcode != 0:
            raise RuntimeError(
                f"xz failed: command {' '.join(argv)} returned {retcode}"
            )


def do_unpack_bare_zstd(
    filename: str,
    destdir: str | None,
) -> None:
    # the suffix may not be ".zst" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["zstd", "-d", filename, "-o", f"./{dest_filename}"]
    log.D(f"about to call zstd: argv={argv}")
    retcode = subprocess.call(argv, cwd=destdir)
    if retcode != 0:
        raise RuntimeError(f"zstd failed: command {' '.join(argv)} returned {retcode}")


def _get_unpack_cmds_for_method(m: UnpackMethod) -> list[str]:
    match m:
        case UnpackMethod.UNKNOWN | UnpackMethod.RAW:
            return []
        case UnpackMethod.GZ:
            return ["gunzip"]
        case UnpackMethod.BZ2:
            return ["bzip2"]
        case UnpackMethod.XZ:
            return ["xz"]
        case UnpackMethod.ZST:
            return ["zstd"]
        case UnpackMethod.TAR | UnpackMethod.TAR_AUTO:
            return ["tar"]
        case UnpackMethod.TAR_GZ:
            return ["tar", "gunzip"]
        case UnpackMethod.TAR_BZ2:
            return ["tar", "bzip2"]
        case UnpackMethod.TAR_XZ:
            return ["tar", "xz"]
        case UnpackMethod.TAR_ZST:
            return ["tar", "zstd"]
        case UnpackMethod.ZIP:
            return ["unzip"]
        case UnpackMethod.AUTO:
            raise ValueError(f"the unpack method {m} must be resolved prior to use")


def ensure_unpack_cmd_for_method(m: UnpackMethod) -> None | NoReturn:
    required_cmds = _get_unpack_cmds_for_method(m)
    if not required_cmds:
        return None

    return prereqs.ensure_cmds(*required_cmds)
