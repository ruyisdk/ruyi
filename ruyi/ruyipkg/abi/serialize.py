"""Deterministic canonical TOML serialization of an ABI report."""

from __future__ import annotations

from typing import Any, Mapping

import tomlkit
from tomlkit import aot, document, inline_table, table
from tomlkit.items import Table

from .model import (
    ABIReport,
    ABIScanError,
    ABISummary,
    AttributeVendorBlob,
    ElfABIRecord,
    ElfType,
    GnuProperty,
    VersionNeed,
)


def dump_abi_report_toml(report: ABIReport) -> str:
    doc = document()
    doc.add("summary", _summary_table(report.summary))

    records = aot()
    for record in report.records:
        records.append(_record_table(record))
    doc.add("record", records)

    if report.errors:
        errors = aot()
        for err in report.errors:
            t = table()
            t.add("path", err.path)
            t.add("reason", err.reason)
            errors.append(t)
        doc.add("error", errors)

    return tomlkit.dumps(doc)


def load_abi_report_toml(text: str) -> ABIReport:
    """Parse a canonical ``.abi.toml`` sidecar back into an ABIReport.

    This is the exact inverse of dump_abi_report_toml(): every field the
    dumper emits is reconstructed, and the optional keys it omits when empty
    (version_defs, gnu_properties, elf_attributes, the summary
    version_needs/well_known_maxima/parsed_attrs_rollup tables, and errors)
    default back to empty. ``.unwrap()`` turns the tomlkit document into plain
    Python values, which are then narrowed into the frozen model types.
    """
    data: Any = tomlkit.parse(text).unwrap()

    summary = data["summary"]
    records = data.get("record", ())

    return ABIReport(
        records=tuple(_load_record(r) for r in records),
        summary=ABISummary(
            e_machines=tuple(summary["e_machines"]),
            needed=tuple(summary["needed"]),
            version_needs=tuple(
                VersionNeed(
                    vn["soname"],
                    tuple(vn["versions"]),
                    tuple(vn.get("weak_versions", ())),
                )
                for vn in summary.get("version_needs", ())
            ),
            well_known_maxima=dict(summary.get("well_known_maxima", {})),
            parsed_attrs_rollup=dict(summary.get("parsed_attrs_rollup", {})),
            elf_count=summary["elf_count"],
            file_count=summary["file_count"],
            excluded_count=summary["excluded_count"],
        ),
        errors=tuple(
            ABIScanError(err["path"], err["reason"]) for err in data.get("error", ())
        ),
    )


def _load_record(record: Any) -> ElfABIRecord:
    return ElfABIRecord(
        paths=tuple(record["paths"]),
        sha256=record["sha256"],
        e_machine=record["e_machine"],
        elf_class=record["elf_class"],
        endianness=record["endianness"],
        elf_type=ElfType(record["elf_type"]),
        is_dynamic=record["is_dynamic"],
        interpreter=record.get("interpreter"),
        soname=record.get("soname") or None,
        needed=tuple(record["needed"]),
        version_needs=tuple(
            VersionNeed(
                vn["soname"],
                tuple(vn["versions"]),
                tuple(vn.get("weak_versions", ())),
            )
            for vn in record.get("version_needs", ())
        ),
        version_defs=tuple(record.get("version_defs", ())),
        needs_unversioned=record["needs_unversioned"],
        gnu_properties=tuple(
            GnuProperty(p["pr_type"], p["data_hex"], p["truncated"])
            for p in record.get("gnu_properties", ())
        ),
        elf_attributes=tuple(
            AttributeVendorBlob(a["vendor"], a["data_hex"], a["truncated"])
            for a in record.get("elf_attributes", ())
        ),
        parsed_attrs=dict(record["parsed_attrs"]),
    )


def _summary_table(summary: ABISummary) -> Table:
    t = table()
    t.add("e_machines", list(summary.e_machines))
    t.add("needed", list(summary.needed))
    t.add("elf_count", summary.elf_count)
    t.add("file_count", summary.file_count)
    t.add("excluded_count", summary.excluded_count)

    if summary.well_known_maxima:
        wk = table()
        for key in sorted(summary.well_known_maxima):
            wk.add(key, summary.well_known_maxima[key])
        t.add("well_known_maxima", wk)

    if summary.parsed_attrs_rollup:
        roll = table()
        for key in sorted(summary.parsed_attrs_rollup):
            roll.add(key, _to_toml(summary.parsed_attrs_rollup[key]))
        t.add("parsed_attrs_rollup", roll)

    if summary.version_needs:
        vns = aot()
        for vn in summary.version_needs:
            sub = table()
            sub.add("soname", vn.soname)
            sub.add("versions", list(vn.versions))
            if vn.weak_versions:
                sub.add("weak_versions", list(vn.weak_versions))
            vns.append(sub)
        t.add("version_needs", vns)

    return t


def _record_table(record: ElfABIRecord) -> Table:
    t = table()
    t.add("paths", list(record.paths))
    t.add("sha256", record.sha256)
    t.add("e_machine", record.e_machine)
    t.add("elf_class", record.elf_class)
    t.add("endianness", record.endianness)
    t.add("elf_type", str(record.elf_type))
    t.add("is_dynamic", record.is_dynamic)
    if record.interpreter is not None:
        t.add("interpreter", record.interpreter)
    t.add("soname", record.soname or "")
    t.add("needed", list(record.needed))
    t.add("needs_unversioned", record.needs_unversioned)

    if record.version_defs:
        t.add("version_defs", list(record.version_defs))

    pa = inline_table()
    for key in sorted(record.parsed_attrs):
        pa[key] = record.parsed_attrs[key]
    t.add("parsed_attrs", pa)

    if record.version_needs:
        vns = aot()
        for vn in record.version_needs:
            sub = table()
            sub.add("soname", vn.soname)
            sub.add("versions", list(vn.versions))
            if vn.weak_versions:
                sub.add("weak_versions", list(vn.weak_versions))
            vns.append(sub)
        t.add("version_needs", vns)

    if record.gnu_properties:
        props = aot()
        for prop in sorted(
            record.gnu_properties, key=lambda p: (p.pr_type, p.data_hex)
        ):
            sub = table()
            sub.add("pr_type", prop.pr_type)
            sub.add("data_hex", prop.data_hex)
            sub.add("truncated", prop.truncated)
            props.append(sub)
        t.add("gnu_properties", props)

    if record.elf_attributes:
        attrs = aot()
        for attr in sorted(record.elf_attributes, key=lambda a: (a.vendor, a.data_hex)):
            sub = table()
            sub.add("vendor", attr.vendor)
            sub.add("data_hex", attr.data_hex)
            sub.add("truncated", attr.truncated)
            attrs.append(sub)
        t.add("elf_attributes", attrs)

    return t


def _to_toml(value: object) -> object:
    """Convert nested rollup values (dicts/lists/scalars) to tomlkit items."""
    if isinstance(value, Mapping):
        it = inline_table()
        for key in sorted(value):
            it[key] = _to_toml(value[key])
        return it
    if isinstance(value, (list, tuple)):
        return [_to_toml(v) for v in value]
    return value
