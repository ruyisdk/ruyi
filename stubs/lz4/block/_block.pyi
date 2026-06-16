from _typeshed import ReadableBuffer

HC_LEVEL_MIN: int
HC_LEVEL_DEFAULT: int
HC_LEVEL_OPT_MIN: int
HC_LEVEL_MAX: int

class LZ4BlockError(Exception): ...

def compress(
    source: ReadableBuffer,
    mode: str = "default",
    acceleration: int = 1,
    compression: int = 9,
    store_size: bool = True,
    return_bytearray: bool = False,
    dict: ReadableBuffer | None = None,
) -> bytes | bytearray: ...
def decompress(
    source: ReadableBuffer,
    uncompressed_size: int = -1,
    return_bytearray: bool = False,
    dict: ReadableBuffer | None = None,
) -> bytes | bytearray: ...
