from collections.abc import Generator
from contextlib import contextmanager
import mmap
import os
import shutil
import subprocess
from typing import Any, BinaryIO, NoReturn, Protocol


from ..i18n import _
from ..log import RuyiLogger
from ..utils import ar, prereqs
from .unpack_method import (
    UnpackMethod,
    UnrecognizedPackFormatError,
    determine_unpack_method,
)


class StreamReader(Protocol):
    def read(self, n: int = -1, /) -> bytes: ...
    def seekable(self) -> bool: ...
    def seek(self, n: int, whence: int = 0, /) -> Any: ...


def do_unpack(
    logger: RuyiLogger,
    filename: str,
    dest: str | os.PathLike[Any] | None,
    strip_components: int,
    unpack_method: UnpackMethod,
    stream: BinaryIO | StreamReader | None = None,
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
    stream: BinaryIO | StreamReader | None = None,
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
    stream: StreamReader | None = None,
    prefixes_to_unpack: list[str] | None = None,
) -> None:
    argv = ["tar", "-x"]

    wrapped_stream = None
    if stream is not None:
        wrapped_stream = _wrap_decompressed(stream, unpack_method)
        filename = "-"
    elif unpack_method not in (UnpackMethod.TAR, UnpackMethod.TAR_AUTO):
        logger.D(f"decompressing {unpack_method} for tar: {filename}")
        wrapped_stream = open_decompressed(filename, unpack_method)
        filename = "-"

    stdin: int | None = None
    if filename == "-":
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
    if wrapped_stream is None:
        retcode = p.wait()
    else:
        assert p.stdin is not None

        bufsize = 4 * mmap.PAGESIZE
        with wrapped_stream as s:
            while True:
                buf = s.read(bufsize)
                if not buf:
                    break
                p.stdin.write(buf)
        p.stdin.close()
        retcode = p.wait()

    if retcode != 0:
        raise RuntimeError(
            _("untar failed: command {cmd} returned {retcode}").format(
                cmd=" ".join(argv),
                retcode=retcode,
            )
        )


@contextmanager
def open_decompressed(
    filename: str,
    unpack_method: UnpackMethod,
) -> Generator[StreamReader, None, None]:
    match unpack_method:
        case UnpackMethod.TAR_GZ:
            import gzip

            gzipFile = gzip.GzipFile(filename, "rb")
            try:
                yield gzipFile
            finally:
                gzipFile.close()
        case UnpackMethod.TAR_BZ2:
            import bz2

            bz2File = bz2.BZ2File(filename, "rb")
            try:
                yield bz2File
            finally:
                bz2File.close()
        case UnpackMethod.TAR_XZ:
            import lzma

            lzmaFile = lzma.LZMAFile(filename, "rb")
            try:
                yield lzmaFile
            finally:
                lzmaFile.close()
        case UnpackMethod.TAR_ZST:
            import zstandard

            zstFile = zstandard.ZstdDecompressor().stream_reader(open(filename, "rb"))
            try:
                yield zstFile
            finally:
                zstFile.close()  # type: ignore[no-untyped-call]  # this is weird
        case UnpackMethod.TAR_LZ4:
            import lz4.frame

            lz4File = lz4.frame.LZ4FrameFile(filename, "rb")
            try:
                yield lz4File
            finally:
                lz4File.close()
        case _:
            raise ValueError(
                f"do_unpack_tar cannot handle non-tar unpack method {unpack_method}"
            )


@contextmanager
def _wrap_decompressed(
    stream: StreamReader,
    unpack_method: UnpackMethod,
) -> Generator[StreamReader, None, None]:
    match unpack_method:
        case UnpackMethod.TAR | UnpackMethod.TAR_AUTO:
            yield stream
        case UnpackMethod.TAR_GZ:
            import gzip

            gzipFile = gzip.GzipFile(fileobj=stream, mode="rb")
            try:
                yield gzipFile
            finally:
                gzipFile.close()
        case UnpackMethod.TAR_BZ2:
            import bz2

            bz2File = bz2.BZ2File(stream, "rb")
            try:
                yield bz2File
            finally:
                bz2File.close()
        case UnpackMethod.TAR_XZ:
            import lzma

            lzmaFile = lzma.LZMAFile(stream, "rb")  # type: ignore[arg-type]  # in fact only read() is used
            try:
                yield lzmaFile
            finally:
                lzmaFile.close()
        case UnpackMethod.TAR_ZST:
            import zstandard

            zstFile = zstandard.ZstdDecompressor().stream_reader(stream)  # type: ignore[arg-type]  # in fact only read() is used
            try:
                yield zstFile
            finally:
                zstFile.close()  # type: ignore[no-untyped-call]  # this is weird
        case UnpackMethod.TAR_LZ4:
            import lz4.frame

            lz4File = lz4.frame.LZ4FrameFile(stream)
            try:
                yield lz4File
            finally:
                lz4File.close()
        case _:
            raise ValueError(
                f"do_unpack_tar cannot handle non-tar unpack method {unpack_method}"
            )


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
        raise RuntimeError(
            _("unzip failed: command {cmd} returned {retcode}").format(
                cmd=" ".join(argv),
                retcode=retcode,
            )
        )


def _do_unpack_bare_gz(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    if destdir is not None:
        os.chdir(destdir)

    import gzip

    logger.D(f"decompressing gzip: {filename}")
    with gzip.open(filename, "rb") as src, open(dest_filename, "wb") as out:
        shutil.copyfileobj(src, out)


def _do_unpack_bare_bzip2(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    if destdir is not None:
        os.chdir(destdir)

    import bz2

    logger.D(f"decompressing bzip2: {filename}")
    with bz2.open(filename, "rb") as src, open(dest_filename, "wb") as out:
        shutil.copyfileobj(src, out)


def _do_unpack_bare_lz4(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    if destdir is not None:
        os.chdir(destdir)

    import lz4.frame

    logger.D(f"decompressing lz4: {filename}")
    with lz4.frame.open(filename, "rb") as src, open(dest_filename, "wb") as out:
        shutil.copyfileobj(src, out)


def _do_unpack_bare_xz(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    if destdir is not None:
        os.chdir(destdir)

    import lzma

    logger.D(f"decompressing xz: {filename}")
    with lzma.open(filename, "rb") as src, open(dest_filename, "wb") as out:
        shutil.copyfileobj(src, out)


def _do_unpack_bare_zstd(
    logger: RuyiLogger,
    filename: str,
    destdir: str | os.PathLike[Any] | None,
) -> None:
    dest_filename = os.path.splitext(os.path.basename(filename))[0]

    if destdir is not None:
        os.chdir(destdir)

    import zstandard

    logger.D(f"decompressing zstd: {filename}")
    dctx = zstandard.ZstdDecompressor()
    with open(filename, "rb") as src, open(dest_filename, "wb") as out:
        dctx.copy_stream(src, out)


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

    raise RuntimeError(
        _("file '{filename}' does not appear to be a deb").format(
            filename=filename,
        )
    )


def _get_unpack_cmds_for_method(m: UnpackMethod) -> list[str]:
    match m:
        case (
            UnpackMethod.UNKNOWN
            | UnpackMethod.RAW
            | UnpackMethod.DEB
            | UnpackMethod.GZ
            | UnpackMethod.BZ2
            | UnpackMethod.LZ4
            | UnpackMethod.XZ
            | UnpackMethod.ZST
        ):
            return []
        case (
            UnpackMethod.TAR
            | UnpackMethod.TAR_AUTO
            | UnpackMethod.TAR_GZ
            | UnpackMethod.TAR_BZ2
            | UnpackMethod.TAR_LZ4
            | UnpackMethod.TAR_XZ
            | UnpackMethod.TAR_ZST
        ):
            return ["tar"]
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
