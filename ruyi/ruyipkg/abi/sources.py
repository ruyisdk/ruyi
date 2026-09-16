"""Source abstraction yielding ELF-candidate members from dirs or archives."""

from __future__ import annotations

import abc
import functools
import pathlib
from typing import BinaryIO, Callable, cast, Iterator, TYPE_CHECKING

from ..unpack_method import UnpackMethod, determine_unpack_method

if TYPE_CHECKING:
    import tarfile

# ``(path, declared_size, read)``. The reader is a lazy view over the member
# and must be called before requesting the next entry, while the source is
# still positioned on it; excluded or oversized members can then be skipped
# without ever reading their contents.
MemberEntry = tuple[str, "int | None", Callable[[], bytes]]

_TAR_METHODS = frozenset(
    {
        UnpackMethod.TAR,
        UnpackMethod.TAR_AUTO,
        UnpackMethod.TAR_GZ,
        UnpackMethod.TAR_BZ2,
        UnpackMethod.TAR_LZ4,
        UnpackMethod.TAR_XZ,
        UnpackMethod.TAR_ZST,
    }
)


def _path_reader(path: pathlib.Path) -> Callable[[], bytes]:
    return lambda: path.read_bytes()


def _bytes_reader(data: bytes) -> Callable[[], bytes]:
    return lambda: data


class ABISource(abc.ABC):
    @abc.abstractmethod
    def iter_members(self) -> Iterator[MemberEntry]: ...

    @staticmethod
    def from_directory(path: pathlib.Path | str) -> "ABISource":
        return _DirectorySource(pathlib.Path(path))

    @staticmethod
    def from_archive(
        path: pathlib.Path | str,
        unpack_method: UnpackMethod = UnpackMethod.AUTO,
    ) -> "ABISource":
        return _ArchiveSource(pathlib.Path(path), unpack_method)


class _DirectorySource(ABISource):
    def __init__(self, root: pathlib.Path) -> None:
        self._root = root

    def iter_members(self) -> Iterator[MemberEntry]:
        for p in sorted(self._root.rglob("*")):
            if p.is_symlink() or not p.is_file():
                continue
            rel = p.relative_to(self._root).as_posix()
            size = p.stat().st_size
            yield rel, size, _path_reader(p)


class _ArchiveSource(ABISource):
    def __init__(self, path: pathlib.Path, unpack_method: UnpackMethod) -> None:
        method = unpack_method
        if method in (UnpackMethod.AUTO, UnpackMethod.TAR_AUTO):
            method = determine_unpack_method(path.name)
        self._path = path
        self._method = method

    def iter_members(self) -> Iterator[MemberEntry]:
        if self._method in _TAR_METHODS:
            yield from self._iter_tar()
        elif self._method == UnpackMethod.ZIP:
            yield from self._iter_zip()
        elif self._method == UnpackMethod.DEB:
            yield from self._iter_deb()
        elif self._method == UnpackMethod.RAW:
            data = self._path.read_bytes()
            yield self._path.name, len(data), _bytes_reader(data)
        else:
            raise ValueError(f"unsupported unpack method for ABI scan: {self._method}")

    def _iter_tar(self) -> Iterator[MemberEntry]:
        import tarfile

        from ..unpack import open_decompressed

        if self._method in (UnpackMethod.TAR_ZST, UnpackMethod.TAR_LZ4):
            # zstd/lz4 streams are not seekable, so parse the tar sequentially
            # (``r|``) while keeping the decompressor open for the duration of
            # the iteration. Member contents are pulled lazily by the consumer,
            # so excluded or oversized members are never materialized.
            with open_decompressed(str(self._path), self._method) as stream:
                fileobj = cast("BinaryIO", stream)
                with tarfile.open(fileobj=fileobj, mode="r|") as tf:
                    yield from self._iter_tar_members(tf)
        else:
            with tarfile.open(str(self._path), mode="r:*") as tf:
                yield from self._iter_tar_members(tf)

    @staticmethod
    def _iter_tar_members(tf: "tarfile.TarFile") -> Iterator[MemberEntry]:
        for member in tf:
            if not member.isreg():
                continue
            extracted = tf.extractfile(member)
            if extracted is None:
                yield member.name, member.size, _bytes_reader(b"")
                continue
            # Hand out the bound ``read`` so the caller can decide whether the
            # member is worth reading at all.
            yield member.name, member.size, extracted.read

    def _iter_zip(self) -> Iterator[MemberEntry]:
        import zipfile

        with zipfile.ZipFile(self._path) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                # Defer the actual decompression until the consumer asks for
                # the member; it may be excluded or over the size limit.
                yield info.filename, info.file_size, functools.partial(zf.read, info)

    def _iter_deb(self) -> Iterator[MemberEntry]:
        import tarfile

        import arpy

        from ..unpack import _wrap_decompressed

        ar = arpy.Archive(str(self._path))
        try:
            for entry in ar:
                name = entry.header.name
                if not name.startswith(b"data.tar"):
                    continue
                # The payload may itself be compressed (data.tar.zst,
                # data.tar.xz, ...), so run it through the shared
                # decompression machinery and parse the result as a
                # sequential tar stream; the ar entry is read lazily.
                method = determine_unpack_method(name.decode("ascii", "replace"))
                with _wrap_decompressed(entry, method) as decompressed:
                    fileobj = cast("BinaryIO", decompressed)
                    with tarfile.open(fileobj=fileobj, mode="r|") as tf:
                        yield from self._iter_tar_members(tf)
                return
        finally:
            ar.close()
