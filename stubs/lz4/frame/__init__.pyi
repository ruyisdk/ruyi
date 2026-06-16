import _compression
import io
import os
import types
from _typeshed import ReadableBuffer
from typing import IO, Literal, Protocol, overload

from ._frame import (
    BLOCKSIZE_DEFAULT as BLOCKSIZE_DEFAULT,
    BLOCKSIZE_MAX64KB as BLOCKSIZE_MAX64KB,
    BLOCKSIZE_MAX256KB as BLOCKSIZE_MAX256KB,
    BLOCKSIZE_MAX1MB as BLOCKSIZE_MAX1MB,
    BLOCKSIZE_MAX4MB as BLOCKSIZE_MAX4MB,
    compress as compress,
    compress_begin as compress_begin,
    compress_chunk as compress_chunk,
    compress_flush as compress_flush,
    create_compression_context as create_compression_context,
    create_decompression_context as create_decompression_context,
    decompress as decompress,
    decompress_chunk as decompress_chunk,
    get_frame_info as get_frame_info,
    reset_decompression_context as reset_decompression_context,
)

class _HasRead(Protocol):
    def read(self, n: int = -1, /) -> bytes: ...

COMPRESSIONLEVEL_MIN: int
COMPRESSIONLEVEL_MINHC: int
COMPRESSIONLEVEL_MAX: int

class LZ4FrameCompressor:
    block_size: int
    block_linked: bool
    compression_level: int
    content_checksum: bool
    block_checksum: bool
    auto_flush: bool
    return_bytearray: bool

    def __init__(
        self,
        block_size: int = BLOCKSIZE_DEFAULT,
        block_linked: bool = True,
        compression_level: int = COMPRESSIONLEVEL_MIN,
        content_checksum: bool = False,
        block_checksum: bool = False,
        auto_flush: bool = False,
        return_bytearray: bool = False,
    ) -> None: ...
    def __enter__(self) -> LZ4FrameCompressor: ...
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None: ...
    def begin(self, source_size: int = 0) -> bytes | bytearray: ...
    def compress(self, data: ReadableBuffer) -> bytes | bytearray: ...  # noqa: F811
    def flush(self) -> bytes | bytearray: ...
    def reset(self) -> None: ...
    def has_context(self) -> bool: ...
    def started(self) -> bool: ...

class LZ4FrameDecompressor:
    eof: bool
    needs_input: bool
    unused_data: bytes | None

    def __init__(self, return_bytearray: bool = False) -> None: ...
    def __enter__(self) -> LZ4FrameDecompressor: ...
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None: ...
    def reset(self) -> None: ...
    def decompress(  # noqa: F811
        self, data: ReadableBuffer, max_length: int = -1
    ) -> bytes | bytearray: ...

class LZ4FrameFile(_compression.BaseStream):
    mode: str

    def __init__(
        self,
        filename: str | bytes | os.PathLike[str] | _HasRead | None = None,
        mode: str = "r",
        block_size: int = BLOCKSIZE_DEFAULT,
        block_linked: bool = True,
        compression_level: int = COMPRESSIONLEVEL_MIN,
        content_checksum: bool = False,
        block_checksum: bool = False,
        auto_flush: bool = False,
        return_bytearray: bool = False,
        source_size: int = 0,
    ) -> None: ...
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...
    def fileno(self) -> int: ...
    def seekable(self) -> bool: ...
    def readable(self) -> bool: ...
    def writable(self) -> bool: ...
    def peek(self, size: int = -1) -> bytes: ...
    def readall(self) -> bytes: ...
    def read(self, size: int | None = -1) -> bytes: ...
    def read1(self, size: int | None = -1) -> bytes: ...
    def readline(self, size: int | None = -1) -> bytes: ...
    def write(self, data: ReadableBuffer) -> int: ...
    def flush(self) -> None: ...
    def seek(self, offset: int, whence: int = 0) -> int: ...
    def tell(self) -> int: ...

@overload
def open(
    filename: str | bytes | os.PathLike[str] | _HasRead,
    mode: Literal["r", "rb", "w", "wb", "x", "xb", "a", "ab"] = "rb",
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    *,
    block_size: int = BLOCKSIZE_DEFAULT,
    block_linked: bool = True,
    compression_level: int = COMPRESSIONLEVEL_MIN,
    content_checksum: bool = False,
    block_checksum: bool = False,
    auto_flush: bool = False,
    return_bytearray: bool = False,
    source_size: int = 0,
) -> IO[bytes]: ...
@overload
def open(
    filename: str | bytes | os.PathLike[str] | _HasRead,
    mode: Literal["rt", "wt", "xt", "at"],
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
    *,
    block_size: int = BLOCKSIZE_DEFAULT,
    block_linked: bool = True,
    compression_level: int = COMPRESSIONLEVEL_MIN,
    content_checksum: bool = False,
    block_checksum: bool = False,
    auto_flush: bool = False,
    return_bytearray: bool = False,
    source_size: int = 0,
) -> io.TextIOWrapper: ...
