"""Data model for ELF ABI compatibility scanning."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

DEFAULT_MAX_MEMBER_BYTES = 256 * 1024 * 1024
DEFAULT_MAX_RAW_ATTR_BYTES = 4096


class ElfType(StrEnum):
    EXEC = "exec"
    DYN = "dyn"
    REL = "rel"
    CORE = "core"
    OTHER = "other"


@dataclass(frozen=True)
class VersionNeed:
    soname: str
    versions: tuple[str, ...]


@dataclass(frozen=True)
class GnuProperty:
    pr_type: int
    data_hex: str
    truncated: bool


@dataclass(frozen=True)
class AttributeVendorBlob:
    vendor: str
    data_hex: str
    truncated: bool


@dataclass(frozen=True)
class ElfABIRecord:
    paths: tuple[str, ...]
    sha256: str
    e_machine: int
    elf_class: int
    endianness: str
    elf_type: ElfType
    is_dynamic: bool
    interpreter: str | None
    soname: str | None
    needed: tuple[str, ...]
    version_needs: tuple[VersionNeed, ...]
    needs_unversioned: bool
    gnu_properties: tuple[GnuProperty, ...]
    elf_attributes: tuple[AttributeVendorBlob, ...]
    parsed_attrs: Mapping[str, str | int | bool]


@dataclass(frozen=True)
class ABISummary:
    e_machines: tuple[int, ...]
    needed: tuple[str, ...]
    version_needs: tuple[VersionNeed, ...]
    well_known_maxima: Mapping[str, str]
    parsed_attrs_rollup: Mapping[str, object]
    elf_count: int
    file_count: int
    excluded_count: int


@dataclass(frozen=True)
class ABIScanError:
    path: str
    reason: str


@dataclass(frozen=True)
class ABIReport:
    records: tuple[ElfABIRecord, ...]
    summary: ABISummary
    errors: tuple[ABIScanError, ...]
