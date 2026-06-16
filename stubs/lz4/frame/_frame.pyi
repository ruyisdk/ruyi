from _typeshed import ReadableBuffer

BLOCKSIZE_DEFAULT: int
BLOCKSIZE_MAX64KB: int
BLOCKSIZE_MAX256KB: int
BLOCKSIZE_MAX1MB: int
BLOCKSIZE_MAX4MB: int

class _CompressionContext: ...
class _DecompressionContext: ...

def compress(
    data: ReadableBuffer,
    compression_level: int = 0,
    block_size: int = 0,
    content_checksum: bool = False,
    block_checksum: bool = False,
    block_linked: bool = True,
    store_size: bool = True,
    return_bytearray: bool = False,
) -> bytes | bytearray: ...
def decompress(
    data: ReadableBuffer,
    return_bytearray: bool = False,
    return_bytes_read: bool = False,
) -> bytes | bytearray | tuple[bytes | bytearray, int]: ...
def create_compression_context() -> _CompressionContext: ...
def compress_begin(
    context: _CompressionContext,
    source_size: int = 0,
    block_size: int = 0,
    compression_level: int = 0,
    content_checksum: bool = False,
    block_checksum: bool = False,
    block_linked: bool = False,
    auto_flush: bool = True,
    return_bytearray: bool = False,
) -> bytes | bytearray: ...
def compress_chunk(
    context: _CompressionContext,
    data: ReadableBuffer,
    return_bytearray: bool = False,
) -> bytes | bytearray: ...
def compress_flush(
    context: _CompressionContext,
    end_frame: bool = True,
    return_bytearray: bool = False,
) -> bytes | bytearray: ...
def create_decompression_context() -> _DecompressionContext: ...
def reset_decompression_context(context: _DecompressionContext) -> None: ...
def decompress_chunk(
    context: _DecompressionContext,
    data: ReadableBuffer,
    max_length: int = -1,
    return_bytearray: bool = False,
) -> tuple[bytes | bytearray, int, bool]: ...
def get_frame_info(data: ReadableBuffer) -> dict[str, int | bool]: ...
