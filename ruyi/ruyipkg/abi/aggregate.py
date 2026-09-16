"""Aggregate per-ELF records into a package-level ABI summary."""

from __future__ import annotations

from typing import Sequence

from .model import ABISummary, ElfABIRecord, VersionNeed

_WELL_KNOWN_PREFIXES = ("GLIBC", "GLIBCXX", "CXXABI", "ZLIB", "GCC")


def _version_key(version: str) -> tuple[object, ...]:
    parts: list[object] = []
    for component in version.split("."):
        if component.isdigit():
            parts.append((0, int(component)))
        else:
            parts.append((1, component))
    return tuple(parts)


def build_summary(
    records: Sequence[ElfABIRecord],
    *,
    file_count: int,
    excluded_count: int,
) -> ABISummary:
    from .interp import get_interpreter

    e_machines = tuple(sorted({r.e_machine for r in records}))

    needed_set: set[str] = set()
    for r in records:
        needed_set.update(r.needed)
    needed = tuple(sorted(needed_set))

    versions_by_soname: dict[str, set[str]] = {}
    for r in records:
        for vn in r.version_needs:
            versions_by_soname.setdefault(vn.soname, set()).update(vn.versions)
    version_needs = tuple(
        VersionNeed(soname=soname, versions=tuple(sorted(vers)))
        for soname, vers in sorted(versions_by_soname.items())
    )

    all_versions = [v for vn in version_needs for v in vn.versions]
    well_known_maxima: dict[str, str] = {}
    for prefix in _WELL_KNOWN_PREFIXES:
        candidates = [
            v[len(prefix) + 1 :]
            for v in all_versions
            if v.startswith(prefix + "_") and v[len(prefix) + 1 :]
        ]
        # Only keep purely version-like suffixes (leading digit).
        candidates = [c for c in candidates if c[:1].isdigit()]
        if candidates:
            well_known_maxima[prefix] = max(candidates, key=_version_key)

    rollup: dict[str, object] = {}
    by_machine: dict[int, list[ElfABIRecord]] = {}
    for r in records:
        by_machine.setdefault(r.e_machine, []).append(r)
    for machine, group in by_machine.items():
        impl = get_interpreter(machine)
        if impl is None:
            continue
        merged = impl.rollup([r.parsed_attrs for r in group])
        if merged:
            rollup[str(machine)] = merged

    return ABISummary(
        e_machines=e_machines,
        needed=needed,
        version_needs=version_needs,
        well_known_maxima=well_known_maxima,
        parsed_attrs_rollup=rollup,
        elf_count=len(records),
        file_count=file_count,
        excluded_count=excluded_count,
    )
