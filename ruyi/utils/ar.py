from contextlib import AbstractContextManager
from typing import BinaryIO, TYPE_CHECKING

if TYPE_CHECKING:
    from types import TracebackType

import arpy


class ArpyArchiveWrapper(arpy.Archive, AbstractContextManager["arpy.Archive"]):
    """Compatibility context manager shim for arpy.Archive, for working across
    arpy 1.x and 2.x."""

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
