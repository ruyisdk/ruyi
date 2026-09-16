"""Per-ELF fact extraction, combining raw capture and interpretation."""

from __future__ import annotations

import dataclasses
import hashlib
import io
from typing import BinaryIO, Sequence, TYPE_CHECKING

from ...i18n import _
from ...log import RuyiLogger
from .model import (
    ABIReport,
    ABIScanError,
    DEFAULT_MAX_MEMBER_BYTES,
    DEFAULT_MAX_RAW_ATTR_BYTES,
    ElfABIRecord,
    ElfType,
    VersionNeed,
)

if TYPE_CHECKING:
    from .sources import ABISource

_E_TYPE_MAP = {
    "ET_EXEC": ElfType.EXEC,
    "ET_DYN": ElfType.DYN,
    "ET_REL": ElfType.REL,
    "ET_CORE": ElfType.CORE,
}


def _e_machine_int(value: object) -> int:
    if isinstance(value, int):
        return value
    from elftools.elf.enums import ENUM_E_MACHINE

    mapped = ENUM_E_MACHINE.get(str(value))
    return mapped if isinstance(mapped, int) else 0


def _map_e_type(value: object) -> ElfType:
    if isinstance(value, str):
        return _E_TYPE_MAP.get(value, ElfType.OTHER)
    return ElfType.OTHER


def scan_elf_stream(
    stream: BinaryIO,
    *,
    paths: tuple[str, ...],
    sha256: str,
    max_raw_attr_bytes: int,
) -> tuple[ElfABIRecord | None, list[ABIScanError]]:
    from elftools.elf.elffile import ELFFile

    from .containers import (
        parse_attribute_vendor_blobs,
        parse_gnu_property_note_section,
    )
    from .interp import get_interpreter

    errors: list[ABIScanError] = []

    try:
        elf = ELFFile(stream)
    except Exception as exc:  # noqa: BLE001  - any parse failure is non-fatal
        return None, [ABIScanError(paths[0], f"not a valid ELF: {exc}")]

    e_machine = _e_machine_int(elf.header["e_machine"])
    elf_class = elf.elfclass
    little_endian = elf.little_endian
    elf_type = _map_e_type(elf.header["e_type"])

    interpreter: str | None = None
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_INTERP":
            interpreter = seg.get_interp_name()  # type: ignore[attr-defined]
            break

    needed: tuple[str, ...] = ()
    soname: str | None = None
    is_dynamic = False
    dynamic = elf.get_section_by_name(".dynamic")
    if dynamic is not None:
        is_dynamic = True
        needed = tuple(t.needed for t in dynamic.iter_tags("DT_NEEDED"))  # type: ignore[attr-defined]
        sonames = [t.soname for t in dynamic.iter_tags("DT_SONAME")]  # type: ignore[attr-defined]
        soname = sonames[0] if sonames else None

    version_needs: list[VersionNeed] = []
    verneed = elf.get_section_by_name(".gnu.version_r")
    if verneed is not None:
        for vn, aux in verneed.iter_versions():  # type: ignore[attr-defined]
            version_needs.append(
                VersionNeed(
                    soname=vn.name,
                    versions=tuple(sorted(a.name for a in aux)),
                )
            )

    needs_unversioned = _compute_needs_unversioned(elf)

    gnu_properties = _extract_gnu_properties(  # type: ignore[no-untyped-call]
        elf, elf_class == 64, little_endian, max_raw_attr_bytes,
        parse_gnu_property_note_section,
    )
    elf_attributes = _extract_attributes(  # type: ignore[no-untyped-call]
        elf, little_endian, max_raw_attr_bytes, parse_attribute_vendor_blobs
    )

    parsed_attrs: dict[str, str | int | bool] = {}
    impl = get_interpreter(e_machine)
    if impl is not None:
        try:
            parsed_attrs = impl.interpret(gnu_properties, elf_attributes)
        except Exception as exc:  # noqa: BLE001
            errors.append(
                ABIScanError(paths[0], f"attribute interpretation failed: {exc}")
            )
            parsed_attrs = {}

    record = ElfABIRecord(
        paths=paths,
        sha256=sha256,
        e_machine=e_machine,
        elf_class=elf_class,
        endianness="little" if little_endian else "big",
        elf_type=elf_type,
        is_dynamic=is_dynamic,
        interpreter=interpreter,
        soname=soname,
        needed=needed,
        version_needs=tuple(version_needs),
        needs_unversioned=needs_unversioned,
        gnu_properties=tuple(gnu_properties),
        elf_attributes=tuple(elf_attributes),
        parsed_attrs=parsed_attrs,
    )
    return record, errors


def _compute_needs_unversioned(elf: object) -> bool:
    dynsym = elf.get_section_by_name(".dynsym")  # type: ignore[attr-defined]
    if dynsym is None:
        return False
    versym = elf.get_section_by_name(".gnu.version")  # type: ignore[attr-defined]
    for i, sym in enumerate(dynsym.iter_symbols()):
        if sym["st_shndx"] != "SHN_UNDEF" or not sym.name:
            continue
        if sym["st_info"]["bind"] not in ("STB_GLOBAL", "STB_WEAK"):
            continue
        if versym is None:
            return True
        ndx = versym.get_symbol(i)["ndx"]
        if ndx in ("VER_NDX_LOCAL", "VER_NDX_GLOBAL", 0, 1):
            return True
    return False


def _extract_gnu_properties(elf, is_64bit, little_endian, max_bytes, parse):  # type: ignore[no-untyped-def]
    section = elf.get_section_by_name(".note.gnu.property")
    if section is None:
        return []
    return parse(
        section.data(),
        is_64bit=is_64bit,
        little_endian=little_endian,
        max_bytes=max_bytes,
    )


def _extract_attributes(elf, little_endian, max_bytes, parse):  # type: ignore[no-untyped-def]
    out = []
    for section in elf.iter_sections():
        if section.name.endswith(".attributes"):
            out.extend(
                parse(section.data(), little_endian=little_endian, max_bytes=max_bytes)
            )
    return out


def scan_source(
    source: "ABISource",
    *,
    logger: RuyiLogger,
    exclude: Sequence[str] = (),
    max_member_bytes: int = DEFAULT_MAX_MEMBER_BYTES,
    max_raw_attr_bytes: int = DEFAULT_MAX_RAW_ATTR_BYTES,
) -> ABIReport:
    from ...utils.pathmatch import build_matcher
    from .aggregate import build_summary

    matcher = build_matcher(exclude)

    seen: dict[str, ElfABIRecord] = {}
    errors: list[ABIScanError] = []
    file_count = 0
    excluded_count = 0

    for path, size, reader in source.iter_members():
        if matcher.is_excluded(path):
            excluded_count += 1
            continue

        file_count += 1

        if size is not None and size > max_member_bytes:
            logger.D(f"skipping oversized member {path} ({size} bytes)")
            errors.append(ABIScanError(path, _("member exceeds size limit")))
            continue

        data = reader()
        if len(data) > max_member_bytes:
            logger.D(f"skipping oversized member {path} ({len(data)} bytes)")
            errors.append(ABIScanError(path, _("member exceeds size limit")))
            continue

        if not data.startswith(b"\x7fELF"):
            continue

        sha = hashlib.sha256(data).hexdigest()
        existing = seen.get(sha)
        if existing is not None:
            if path not in existing.paths:
                merged = tuple(sorted({*existing.paths, path}))
                seen[sha] = dataclasses.replace(existing, paths=merged)
            continue

        record, errs = scan_elf_stream(
            io.BytesIO(data),
            paths=(path,),
            sha256=sha,
            max_raw_attr_bytes=max_raw_attr_bytes,
        )
        errors.extend(errs)
        if record is not None:
            seen[sha] = record

    records = tuple(sorted(seen.values(), key=lambda r: r.sha256))
    summary = build_summary(
        records, file_count=file_count, excluded_count=excluded_count
    )
    logger.D(
        f"ABI scan: {summary.elf_count} distinct ELF(s), "
        f"{file_count} member(s), {excluded_count} excluded"
    )
    return ABIReport(records=records, summary=summary, errors=tuple(errors))
