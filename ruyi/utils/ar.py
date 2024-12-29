from contextlib import AbstractContextManager
from typing import BinaryIO, TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

import arpy


class ArpyArchiveWrapper(arpy.Archive, AbstractContextManager["arpy.Archive"]):
    """Compatibility shim for arpy.Archive, for easy interop with both arpy 1.x
    and 2.x."""

    def __init__(
        self,
        filename: str | None = None,
        fileobj: BinaryIO | None = None,
    ) -> None:
        super().__init__(filename=filename, fileobj=fileobj)

    def __enter__(self) -> arpy.Archive:
        if hasattr(super(), "__enter__"):
            # in case we're working with a newer arpy version that has a
            # non-trivial __enter__ implementation
            return super().__enter__()

        # backport of arpy 2.x __enter__ implementation
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: "TracebackType | None",
    ) -> None:
        if hasattr(super(), "__exit__"):
            return super().__exit__(exc_type, exc_value, traceback)

        # backport of arpy 2.x __exit__ implementation
        self.close()

    def infolist(self) -> list[arpy.ArchiveFileHeader]:
        if hasattr(super(), "infolist"):
            return super().infolist()

        # backport of arpy 2.x infolist()
        self.read_all_headers()
        return [
            header
            for header in self.headers
            if header.type
            in (
                arpy.HEADER_BSD,
                arpy.HEADER_NORMAL,
                arpy.HEADER_GNU,
            )
        ]

    def open(self, name: bytes | arpy.ArchiveFileHeader) -> arpy.ArchiveFileData:
        if hasattr(super(), "open"):
            return super().open(name)

        # backport of arpy 2.x open()
        if isinstance(name, bytes):
            ar_file = self.archived_files.get(name)
            if ar_file is None:
                raise KeyError("There is no item named %r in the archive" % (name,))

            return ar_file

        if name not in self.headers:
            raise KeyError("Provided header does not match this archive")

        return arpy.ArchiveFileData(ar_obj=self, header=name)
