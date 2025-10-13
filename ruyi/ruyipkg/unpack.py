import mmap
import os
import shutil
import subprocess
from typing import Any, BinaryIO, NoReturn, Protocol

from ..log import RuyiLogger
from ..utils import ar, prereqs
from .unpack_method import (
    UnpackMethod,
    UnrecognizedPackFormatError,
    determine_unpack_method,
)


class SupportsRead(Protocol):
    def read(self, n: int = -1, /) -> bytes: ...


def do_unpack(
    logger: RuyiLogger,
    filename: str,
    dest: str | os.PathLike[Any] | None,
    strip_components: int,
    unpack_method: UnpackMethod,
    stream: BinaryIO | SupportsRead | None = None,
    prefixes_to_unpack: list[str] | None = None,
) -> None:
    match unpack_method:
        case UnpackMethod.AUTO:
            raise ValueError("the auto unpack method must be resolved prior to use")
        case UnpackMethod.RAW:
            return _do_copy_raw(filename, dest)
        case (
            UnpackMethod.TAR_AUTO
            | UnpackMethod.TAR
            | UnpackMethod.TAR_BZ2
            | UnpackMethod.TAR_GZ
            | UnpackMethod.TAR_LZ4
            | UnpackMethod.TAR_XZ
            | UnpackMethod.TAR_ZST
        ):
            return _do_unpack_tar(
                logger,
                filename,
                dest,
                strip_components,
                unpack_method,
                stream,
                prefixes_to_unpack,
            )
        case UnpackMethod.ZIP:
            # TODO: handle strip_components somehow; the unzip(1) command currently
            # does not have such support.
            return _do_unpack_zip(logger, filename, dest)
        case UnpackMethod.DEB:
            return _do_unpack_deb(logger, filename, dest)
        case UnpackMethod.GZ:
            # bare gzip file
            return _do_unpack_bare_gz(logger, filename, dest)
        case UnpackMethod.BZ2:
            # bare bzip2 file
            return _do_unpack_bare_bzip2(logger, filename, dest)
        case UnpackMethod.LZ4:
            # bare lz4 file
            return _do_unpack_bare_lz4(logger, filename, dest)
        case UnpackMethod.XZ:
            # bare xz file
            return _do_unpack_bare_xz(logger, filename, dest)
        case UnpackMethod.ZST:
            # bare zstd file
            return _do_unpack_bare_zstd(logger, filename, dest)
        case _:
            raise UnrecognizedPackFormatError(filename)


def do_unpack_or_symlink(
    logger: RuyiLogger,
    filename: str,
    dest: str | os.PathLike[Any] | None,
    strip_components: int,
    unpack_method: UnpackMethod,
    stream: BinaryIO | SupportsRead | None = None,
    prefixes_to_unpack: list[str] | None = None,
) -> None:
    try:
        return do_unpack(
            logger,
            filename,
            dest,
            strip_components,
            unpack_method,
            stream,
            prefixes_to_unpack,
        )
    except UnrecognizedPackFormatError:
        # just symlink into destination
        return do_symlink(filename, dest)


def _do_copy_raw(
    src_path: str,
    destdir: str | os.PathLike[Any] | None,
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
    destdir: str | os.PathLike[Any] | None,
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


def _do_unpack_tar(
    logger: RuyiLogger,
    filename: str,
    dest: str | os.PathLike[Any] | None,
    strip_components: int,
    unpack_method: UnpackMethod,
    stream: SupportsRead | None,
    prefixes_to_unpack: list[str] | None = None,
) -> None:
    argv = ["tar", "-x"]

    match unpack_method:
        case UnpackMethod.TAR | UnpackMethod.TAR_AUTO:
            pass
        case UnpackMethod.TAR_GZ:
            argv.append("-z")
        case UnpackMethod.TAR_BZ2:
            argv.append("-j")
        case UnpackMethod.TAR_LZ4:
            argv.append("--use-compress-program=lz4")
        case UnpackMethod.TAR_XZ:
            argv.append("-J")
        case UnpackMethod.TAR_ZST:
            argv.append("--zstd")
        case _:
            raise ValueError(
                f"do_unpack_tar cannot handle non-tar unpack method {unpack_method}"
            )

    stdin: int | None = None
    if stream is not None:
        filename = "-"
        stdin = subprocess.PIPE

    argv.extend(("-f", filename, f"--strip-components={strip_components}"))
    if prefixes_to_unpack:
        if any(p.startswith("-") for p in prefixes_to_unpack):
            raise ValueError(
                "prefixes_to_unpack must not contain any item starting with '-'"
            )
        argv.extend(prefixes_to_unpack)
    logger.D(f"about to call tar: argv={argv}")
    p = subprocess.Popen(argv, cwd=dest, stdin=stdin)

    retcode: int
    if stream is None:
        retcode = p.wait()
    else:
        # this is only for pleasing the type-checker; it's statically true
        # because the assignment always happens due to the earlier
        # "stream is not None" branch.
        assert p.stdin is not None

        bufsize = 4 * mmap.PAGESIZE
        while True:
            buf = stream.read(bufsize)
            if not buf:
                break
            p.stdin.write(buf)
        p.stdin.close()
        retcode = p.wait()

    if retcode != 0:
        raise RuntimeError(f"untar failed: command {' '.join(argv)} returned {retcode}")


def _do_unpack_zip(
    logger: RuyiLogger,
    filename: str,
    dest: str | os.PathLike[Any] | None,
) -> None:
    argv = ["unzip", filename]
    if dest is not None:
        argv.extend(("-d", str(dest)))
    logger.D(f"about to call unzip: argv={argv}")
    retcode = subprocess.call(argv, cwd=dest)
    if retcode != 0:
        raise RuntimeError(f"unzip failed: command {' '.join(argv)} returned {retcode}")


def _do_unpack_bare_gz(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    # the suffix may not be ".gz" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["gunzip", "-c", filename]
    if destdir is not None:
        os.chdir(destdir)

    logger.D(f"about to call gunzip: argv={argv}")
    with open(dest_filename, "wb") as out:
        retcode = subprocess.call(argv, stdout=out)
        if retcode != 0:
            raise RuntimeError(
                f"gunzip failed: command {' '.join(argv)} returned {retcode}"
            )


def _do_unpack_bare_bzip2(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    # the suffix may not be ".bz2" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["bzip2", "-dc", filename]
    if destdir is not None:
        os.chdir(destdir)

    logger.D(f"about to call bzip2: argv={argv}")
    with open(dest_filename, "wb") as out:
        retcode = subprocess.call(argv, stdout=out)
        if retcode != 0:
            raise RuntimeError(
                f"bzip2 failed: command {' '.join(argv)} returned {retcode}"
            )


def _do_unpack_bare_lz4(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    # the suffix may not be ".lz4" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["lz4", "-dk", filename, f"./{dest_filename}"]
    logger.D(f"about to call lz4: argv={argv}")
    retcode = subprocess.call(argv, cwd=destdir)
    if retcode != 0:
        raise RuntimeError(f"lz4 failed: command {' '.join(argv)} returned {retcode}")


def _do_unpack_bare_xz(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    # the suffix may not be ".xz" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["xz", "-d", "-c", filename]
    if destdir is not None:
        os.chdir(destdir)

    logger.D(f"about to call xz: argv={argv}")
    with open(dest_filename, "wb") as out:
        retcode = subprocess.call(argv, stdout=out)
        if retcode != 0:
            raise RuntimeError(
                f"xz failed: command {' '.join(argv)} returned {retcode}"
            )


def _do_unpack_bare_zstd(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    # the suffix may not be ".zst" so do this generically
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    argv = ["zstd", "-d", filename, "-o", f"./{dest_filename}"]
    logger.D(f"about to call zstd: argv={argv}")
    retcode = subprocess.call(argv, cwd=destdir)
    if retcode != 0:
        raise RuntimeError(f"zstd failed: command {' '.join(argv)} returned {retcode}")


def _do_unpack_deb(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    with ar.ArpyArchiveWrapper(filename) as a:
        for f in a.infolist():
            name = f.name.decode("utf-8")
            if name.startswith("data.tar"):
                inner_unpack_method = determine_unpack_method(name)
                return _do_unpack_tar(
                    logger,
                    name,
                    destdir,
                    0,
                    inner_unpack_method,
                    a.open(f),
                )

    raise RuntimeError(f"file '{filename}' does not appear to be a deb")


def _get_unpack_cmds_for_method(m: UnpackMethod) -> list[str]:
    match m:
        case UnpackMethod.UNKNOWN | UnpackMethod.RAW | UnpackMethod.DEB:
            return []
        case UnpackMethod.GZ:
            return ["gunzip"]
        case UnpackMethod.BZ2:
            return ["bzip2"]
        case UnpackMethod.LZ4:
            return ["lz4"]
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
        case UnpackMethod.TAR_LZ4:
            return ["tar", "lz4"]
        case UnpackMethod.TAR_XZ:
            return ["tar", "xz"]
        case UnpackMethod.TAR_ZST:
            return ["tar", "zstd"]
        case UnpackMethod.ZIP:
            return ["unzip"]
        case UnpackMethod.AUTO:
            raise ValueError(f"the unpack method {m} must be resolved prior to use")


def ensure_unpack_cmd_for_method(
    logger: RuyiLogger,
    m: UnpackMethod,
) -> None | NoReturn:
    required_cmds = _get_unpack_cmds_for_method(m)
    if not required_cmds:
        return None

    return prereqs.ensure_cmds(logger, required_cmds, interactive_retry=True)
