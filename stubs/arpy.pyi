import io
import types
from typing import BinaryIO

HEADER_BSD: int
HEADER_GNU: int
HEADER_GNU_TABLE: int
HEADER_GNU_SYMBOLS: int
HEADER_NORMAL: int
HEADER_TYPES: dict[int, str]
GLOBAL_HEADER_LEN: int
HEADER_LEN: int

class ArchiveFormatError(Exception): ...
class ArchiveAccessError(IOError): ...

class ArchiveFileHeader:
    type: int
    size: int
    timestamp: int
    uid: int | None
    gid: int | None
    mode: int
    offset: int
    name: bytes
    file_offset: int | None
    proxy_name: bytes
    def __init__(self, header: bytes, offset: int) -> None: ...

class ArchiveFileData(io.IOBase):
    header: ArchiveFileHeader
    arobj: Archive
    last_offset: int
    def __init__(self, ar_obj: Archive, header: ArchiveFileHeader) -> None: ...
    def read(self, size: int | None = None) -> bytes: ...
    def tell(self) -> int: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def seekable(self) -> bool: ...
    def __enter__(self) -> ArchiveFileData: ...
    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: types.TracebackType | None,
    ) -> None: ...

class ArchiveFileDataThin(ArchiveFileData):
    file_path: str
    def __init__(self, ar_obj: Archive, header: ArchiveFileHeader) -> None: ...
    def read(self, size: int | None = None) -> bytes: ...

class Archive:
    headers: list[ArchiveFileHeader]
    file: BinaryIO
    position: int
    reached_eof: bool
    file_data_class: type[ArchiveFileData] | type[ArchiveFileDataThin]
    next_header_offset: int
    gnu_table: dict[int, bytes]
    archived_files: dict[bytes, ArchiveFileData]
    def __init__(
        self, filename: str | None = None, fileobj: BinaryIO | None = None
    ) -> None: ...
    def read_next_header(self) -> ArchiveFileHeader | None: ...
    def __next__(self) -> ArchiveFileData: ...
    next = __next__
    def __iter__(self) -> Archive: ...
    def read_all_headers(self) -> None: ...
    def close(self) -> None: ...
    def namelist(self) -> list[bytes]: ...
    def infolist(self) -> list[ArchiveFileHeader]: ...
    def open(self, name: bytes | ArchiveFileHeader) -> ArchiveFileData: ...
    def __enter__(self) -> Archive: ...
    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: types.TracebackType | None,
    ) -> None: ...
