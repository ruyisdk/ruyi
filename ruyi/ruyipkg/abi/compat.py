"""Pure host-vs-package ABI compatibility checking.

No I/O happens here: HostABIReport contains every fact the rules need.
Each rule yields one HostABICompatItem ready for rendering.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .hostprobe import HostABIReport
from .interp import get_interpreter
from .model import ABIReport


@dataclass(frozen=True)
class HostABICompatItem:
    check: str
    compatible: bool | None  # True / False / None = undetermined
    msgid: str
    params: Mapping[str, object]


@dataclass(frozen=True)
class HostABICompatReport:
    items: tuple[HostABICompatItem, ...]

    @property
    def compatible(self) -> bool | None:
        if any(i.compatible is False for i in self.items):
            return False
        if any(i.compatible is None for i in self.items):
            return None
        return True

    def __bool__(self) -> bool:
        """Lenient predicate: True iff nothing is definitely incompatible."""
        return self.compatible is not False

    @property
    def strictly_compatible(self) -> bool:
        return self.compatible is True

    def problems(self) -> tuple[HostABICompatItem, ...]:
        return tuple(i for i in self.items if i.compatible is not True)


def check_host_compatibility(
    package: ABIReport,
    host: HostABIReport,
) -> HostABICompatReport:
    items: list[HostABICompatItem] = []
    items.extend(_check_e_machine(package, host))
    items.extend(_check_interpreters(package, host))
    items.extend(_check_sonames(package, host))
    items.extend(_check_verneeds(package, host))
    items.extend(_check_unversioned(package))
    items.extend(_check_attrs(package, host))
    return HostABICompatReport(items=tuple(items))


def _check_e_machine(
    package: ABIReport, host: HostABIReport
) -> list[HostABICompatItem]:
    if not host.e_machines:
        return [
            HostABICompatItem("e-machine", None, "host architecture is unknown", {})
        ]
    out: list[HostABICompatItem] = []
    ok = set(package.summary.e_machines) <= set(host.e_machines)
    out.append(
        HostABICompatItem(
            "e-machine",
            ok,
            "package targets e_machine(s) {want}, host is {got}",
            {
                "want": sorted(package.summary.e_machines),
                "got": sorted(host.e_machines),
            },
        )
    )
    if host.elf_class:
        mismatched = sum(
            1
            for r in package.records
            if r.elf_class != host.elf_class or r.endianness != host.endianness
        )
        out.append(
            HostABICompatItem(
                "elf-class",
                mismatched == 0,
                "{count} record(s) mismatch host ELF class/endianness",
                {"count": mismatched},
            )
        )
    return out


def _check_interpreters(
    package: ABIReport, host: HostABIReport
) -> list[HostABICompatItem]:
    paths = sorted(
        {r.interpreter for r in package.records if r.interpreter is not None}
    )
    out: list[HostABICompatItem] = []
    for path in paths:
        out.append(
            HostABICompatItem(
                "interp",
                path in host.interpreter_paths_present,
                "package requires interpreter {path}",
                {"path": path},
            )
        )
    return out


def _check_sonames(package: ABIReport, host: HostABIReport) -> list[HostABICompatItem]:
    out: list[HostABICompatItem] = []
    for soname in package.summary.needed:
        out.append(
            HostABICompatItem(
                "soname",
                soname in host.resolvable_sonames,
                "package requires shared library {soname}",
                {"soname": soname},
            )
        )
    return out


def _check_verneeds(package: ABIReport, host: HostABIReport) -> list[HostABICompatItem]:
    needs = package.summary.version_needs
    if not needs:
        return []
    if host.providers is None:
        return [
            HostABICompatItem(
                "verneed", None, "provider library scan is unavailable", {}
            )
        ]
    provided = {
        r.soname: set(r.version_defs)
        for r in host.providers.records
        if r.soname is not None
    }
    out: list[HostABICompatItem] = []
    for vn in needs:
        defs = provided.get(vn.soname)
        if defs is None:
            out.append(
                HostABICompatItem(
                    "verneed",
                    None,
                    "provider of {soname} was not scanned",
                    {"soname": vn.soname},
                )
            )
            continue
        missing = sorted(set(vn.versions) - defs)
        out.append(
            HostABICompatItem(
                "verneed",
                not missing,
                "provider of {soname} lacks version(s) {missing}",
                {"soname": vn.soname, "missing": missing},
            )
        )
    return out


def _check_unversioned(package: ABIReport) -> list[HostABICompatItem]:
    if any(r.needs_unversioned for r in package.records):
        return [
            HostABICompatItem(
                "unversioned", None, "package needs unversioned symbols", {}
            )
        ]
    return []


def _check_attrs(package: ABIReport, host: HostABIReport) -> list[HostABICompatItem]:
    seen: set[tuple[int, tuple[tuple[str, str | int | bool], ...]]] = set()
    out: list[HostABICompatItem] = []
    for record in package.records:
        if not record.parsed_attrs:
            continue
        key = (record.e_machine, _freeze_attrs(record.parsed_attrs))
        if key in seen:
            continue
        seen.add(key)
        interp = get_interpreter(record.e_machine)
        if interp is None:
            out.append(
                HostABICompatItem(
                    "attrs",
                    None,
                    "no attribute interpreter for e_machine {machine}",
                    {"machine": record.e_machine},
                )
            )
            continue
        host_attrs = host.attrs.get(str(record.e_machine), {})
        result = interp.check(host_attrs, record.parsed_attrs)
        out.append(
            HostABICompatItem(
                "attrs",
                result,
                "package requires e_machine {machine} attributes {required}, host has {host}",
                {
                    "machine": record.e_machine,
                    "required": dict(record.parsed_attrs),
                    "host": dict(host_attrs),
                },
            )
        )
    return out


def _freeze_attrs(
    attrs: Mapping[str, str | int | bool],
) -> tuple[tuple[str, str | int | bool], ...]:
    return tuple(sorted(attrs.items()))
