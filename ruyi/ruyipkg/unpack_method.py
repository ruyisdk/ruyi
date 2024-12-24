import enum
import re
import sys
from typing import Final

RE_TARBALL: Final = re.compile(r"\.tar(?:\.gz|\.bz2|\.lz4|\.xz|\.zst)?$")


if sys.version_info >= (3, 11):

    class UnpackMethod(enum.StrEnum):
        UNKNOWN = ""
        AUTO = "auto"
        TAR_AUTO = "tar.auto"

        RAW = "raw"
        GZ = "gz"
        BZ2 = "bz2"
        LZ4 = "lz4"
        XZ = "xz"
        ZST = "zst"

        TAR = "tar"
        TAR_GZ = "tar.gz"
        TAR_BZ2 = "tar.bz2"
        TAR_LZ4 = "tar.lz4"
        TAR_XZ = "tar.xz"
        TAR_ZST = "tar.zst"

        ZIP = "zip"
        DEB = "deb"

else:

    class UnpackMethod(str, enum.Enum):
        UNKNOWN = ""
        AUTO = "auto"
        TAR_AUTO = "tar.auto"

        RAW = "raw"
        GZ = "gz"
        BZ2 = "bz2"
        LZ4 = "lz4"
        XZ = "xz"
        ZST = "zst"

        TAR = "tar"
        TAR_GZ = "tar.gz"
        TAR_BZ2 = "tar.bz2"
        TAR_LZ4 = "tar.lz4"
        TAR_XZ = "tar.xz"
        TAR_ZST = "tar.zst"

        ZIP = "zip"
        DEB = "deb"


class UnrecognizedPackFormatError(Exception):
    def __init__(self, filename: str) -> None:
        self.filename = filename

    def __str__(self) -> str:
        return f"don't know how to unpack file {self.filename}"


def determine_unpack_method(
    filename: str,
) -> UnpackMethod:
    filename_lower = filename.lower()
    if m := RE_TARBALL.search(filename_lower):
        return UnpackMethod(m.group(0)[1:])
    if filename_lower.endswith(".deb"):
        return UnpackMethod.DEB
    if filename_lower.endswith(".zip"):
        return UnpackMethod.ZIP
    if filename_lower.endswith(".gz"):
        # bare gzip file
        return UnpackMethod.GZ
    if filename_lower.endswith(".bz2"):
        # bare bzip2 file
        return UnpackMethod.BZ2
    if filename_lower.endswith(".lz4"):
        # bare lz4 file
        return UnpackMethod.LZ4
    if filename_lower.endswith(".xz"):
        # bare xz file
        return UnpackMethod.XZ
    if filename_lower.endswith(".zst"):
        # bare zstd file
        return UnpackMethod.ZST
    return UnpackMethod.UNKNOWN
