"""ELF ABI compatibility scanning."""

from __future__ import annotations

from .model import (
    ABIReport,
    ABIScanError,
    ABISummary,
    AttributeVendorBlob,
    DEFAULT_MAX_MEMBER_BYTES,
    DEFAULT_MAX_RAW_ATTR_BYTES,
    ElfABIRecord,
    ElfType,
    GnuProperty,
    VersionNeed,
)
from .scanner import scan_source
from .serialize import dump_abi_report_toml
from .sources import ABISource

__all__ = [
    "ABIReport",
    "ABIScanError",
    "ABISummary",
    "ABISource",
    "AttributeVendorBlob",
    "DEFAULT_MAX_MEMBER_BYTES",
    "DEFAULT_MAX_RAW_ATTR_BYTES",
    "ElfABIRecord",
    "ElfType",
    "GnuProperty",
    "VersionNeed",
    "dump_abi_report_toml",
    "scan_source",
]
