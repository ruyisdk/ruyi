"""Tests for host-vs-package ABI compatibility checking (ruyi.ruyipkg.abi.compat)."""

from __future__ import annotations

from ruyi.ruyipkg.abi.aggregate import build_summary
from ruyi.ruyipkg.abi.compat import (
    HostABICompatItem,
    HostABICompatReport,
    check_host_compatibility,
)
from ruyi.ruyipkg.abi.hostprobe import HostABIReport
from ruyi.ruyipkg.abi.model import (
    ABIReport,
    ABIScanError,
    ElfABIRecord,
    ElfType,
    VersionNeed,
)


def _rec(**kw: object) -> ElfABIRecord:
    base: dict[str, object] = {
        "paths": ("bin/x",),
        "sha256": "0",
        "e_machine": 62,
        "elf_class": 64,
        "endianness": "little",
        "elf_type": ElfType.DYN,
        "is_dynamic": True,
        "interpreter": None,
        "soname": None,
        "needed": (),
        "version_needs": (),
        "version_defs": (),
        "needs_unversioned": False,
        "gnu_properties": (),
        "elf_attributes": (),
        "parsed_attrs": {},
    }
    base.update(kw)
    return ElfABIRecord(**base)  # type: ignore[arg-type]


def _report(
    *records: ElfABIRecord, errors: tuple[ABIScanError, ...] = ()
) -> ABIReport:
    return ABIReport(
        records=records,
        summary=build_summary(records, file_count=len(records), excluded_count=0),
        errors=errors,
    )


def _host(**kw: object) -> HostABIReport:
    base: dict[str, object] = {
        "e_machines": frozenset(),
        "elf_class": 0,
        "endianness": "",
        "resolvable_sonames": frozenset(),
        "providers": None,
        "interpreter_paths_present": frozenset(),
        "attrs": {},
    }
    base.update(kw)
    return HostABIReport(**base)  # type: ignore[arg-type]


def _items_of(report: HostABICompatReport, check: str) -> list[HostABICompatItem]:
    return [i for i in report.items if i.check == check]


def test_bool_lenient_and_strict() -> None:
    item_ok = HostABICompatItem(
        "soname", True, "soname resolvable: {soname}", {"soname": "libc.so.6"}
    )
    item_unknown = HostABICompatItem(
        "unversioned", None, "package needs unversioned symbols", {}
    )
    item_bad = HostABICompatItem(
        "e-machine",
        False,
        "package targets e_machine {want}, host is {got}",
        {"want": 243, "got": 62},
    )
    assert HostABICompatReport((item_ok,)).compatible is True
    assert bool(HostABICompatReport((item_ok,))) is True
    r = HostABICompatReport((item_ok, item_unknown))
    assert r.compatible is None
    assert bool(r) is True  # lenient predicate
    assert r.strictly_compatible is False
    r = HostABICompatReport((item_ok, item_bad))
    assert r.compatible is False
    assert bool(r) is False


def test_problems_returns_non_true_items() -> None:
    ok = HostABICompatItem("a", True, "ok", {})
    unknown = HostABICompatItem("b", None, "unknown", {})
    bad = HostABICompatItem("c", False, "bad", {})
    report = HostABICompatReport((ok, unknown, bad))
    assert report.problems() == (unknown, bad)


def test_e_machine_subset_ok() -> None:
    pkg = _report(_rec(e_machine=62))
    host = _host(e_machines=frozenset({62, 243}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    assert [i.compatible for i in _items_of(report, "e-machine")] == [True]


def test_e_machine_mismatch() -> None:
    pkg = _report(_rec(e_machine=243))
    host = _host(e_machines=frozenset({62}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    assert [i.compatible for i in _items_of(report, "e-machine")] == [False]


def test_e_machine_unknown_host() -> None:
    pkg = _report(_rec(e_machine=62))
    host = _host(e_machines=frozenset())
    report = check_host_compatibility(pkg, host)
    em = _items_of(report, "e-machine")
    assert len(em) == 1
    assert em[0].compatible is None


def test_elf_class_mismatch() -> None:
    pkg = _report(_rec(e_machine=62, elf_class=32))
    host = _host(e_machines=frozenset({62}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    assert [i.compatible for i in _items_of(report, "elf-class")] == [False]


def test_endianness_mismatch() -> None:
    pkg = _report(_rec(e_machine=62, elf_class=64, endianness="big"))
    host = _host(e_machines=frozenset({62}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    assert [i.compatible for i in _items_of(report, "elf-class")] == [False]


def test_elf_class_match() -> None:
    pkg = _report(_rec(e_machine=62, elf_class=64, endianness="little"))
    host = _host(e_machines=frozenset({62}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    assert [i.compatible for i in _items_of(report, "elf-class")] == [True]


def test_elf_class_skipped_when_host_class_unknown() -> None:
    pkg = _report(_rec(e_machine=62, elf_class=32))
    host = _host(e_machines=frozenset({62}), elf_class=0, endianness="")
    report = check_host_compatibility(pkg, host)
    assert _items_of(report, "elf-class") == []


def test_interpreter_missing_deduped() -> None:
    interp = "/lib/ld-linux-x86-64.so.2"
    pkg = _report(_rec(interpreter=interp), _rec(interpreter=interp))
    host = _host(e_machines=frozenset({62}), interpreter_paths_present=frozenset())
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "interp")
    assert len(items) == 1
    assert items[0].compatible is False


def test_interpreter_present() -> None:
    interp = "/lib/ld-linux-x86-64.so.2"
    pkg = _report(_rec(interpreter=interp))
    host = _host(
        e_machines=frozenset({62}),
        interpreter_paths_present=frozenset({interp}),
    )
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "interp")
    assert len(items) == 1
    assert items[0].compatible is True


def test_soname_missing_is_undetermined() -> None:
    pkg = _report(_rec(needed=("libc.so.6", "libm.so.6")))
    host = _host(
        e_machines=frozenset({62}), resolvable_sonames=frozenset({"libc.so.6"})
    )
    report = check_host_compatibility(pkg, host)
    by_soname = {i.params["soname"]: i.compatible for i in _items_of(report, "soname")}
    assert by_soname == {"libc.so.6": True, "libm.so.6": None}
    # A lookup we could not perform says nothing definite about the host.
    assert report.compatible is None
    assert bool(report) is True


def test_verneed_missing_version() -> None:
    pkg = _report(
        _rec(version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.34", "GLIBC_2.40")),))
    )
    providers = _report(
        _rec(soname="libc.so.6", version_defs=("GLIBC_2.34", "GLIBC_2.35"))
    )
    host = _host(e_machines=frozenset({62}), providers=providers)
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "verneed")
    assert len(items) == 1
    assert items[0].compatible is False
    assert items[0].params["missing"] == ["GLIBC_2.40"]


def test_verneed_satisfied() -> None:
    pkg = _report(_rec(version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.34",)),)))
    providers = _report(
        _rec(soname="libc.so.6", version_defs=("GLIBC_2.34", "GLIBC_2.35"))
    )
    host = _host(e_machines=frozenset({62}), providers=providers)
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "verneed")
    assert len(items) == 1
    assert items[0].compatible is True


def test_verneed_providers_none() -> None:
    pkg = _report(_rec(version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.34",)),)))
    host = _host(e_machines=frozenset({62}), providers=None)
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "verneed")
    assert len(items) == 1
    assert items[0].compatible is None


def test_verneed_soname_unscanned() -> None:
    pkg = _report(_rec(version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.34",)),)))
    providers = _report(_rec(soname="libm.so.6", version_defs=("GLIBC_2.34",)))
    host = _host(e_machines=frozenset({62}), providers=providers)
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "verneed")
    assert len(items) == 1
    assert items[0].compatible is None


def test_unversioned_single_none_item_and_lenient_bool() -> None:
    pkg = _report(
        _rec(e_machine=62, needs_unversioned=True),
        _rec(e_machine=62, needs_unversioned=True),
    )
    host = _host(e_machines=frozenset({62}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "unversioned")
    assert len(items) == 1
    assert items[0].compatible is None
    # Review Focus #6: strictly_compatible never True, but bool() still passes.
    assert report.compatible is None
    assert report.strictly_compatible is False
    assert bool(report) is True


def test_unversioned_absent_no_item() -> None:
    pkg = _report(_rec(e_machine=62, needs_unversioned=False))
    host = _host(e_machines=frozenset({62}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    assert _items_of(report, "unversioned") == []


def test_scan_errors_are_undetermined() -> None:
    pkg = _report(errors=(ABIScanError("bin/broken", "failed to read member"),))
    host = _host(e_machines=frozenset({62}), elf_class=64, endianness="little")
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "scan-error")
    assert len(items) == 1
    assert items[0].compatible is None
    assert items[0].params == {
        "path": "bin/broken",
        "reason": "failed to read member",
    }
    # Missing ABI data must not look strictly compatible.
    assert report.compatible is None
    assert report.strictly_compatible is False
    assert bool(report) is True


def test_attrs_empty_parsed_produce_no_item() -> None:
    pkg = _report(_rec(e_machine=62, parsed_attrs={}))
    host = _host(e_machines=frozenset({62}))
    report = check_host_compatibility(pkg, host)
    assert _items_of(report, "attrs") == []


def test_attrs_no_interpreter_is_none() -> None:
    pkg = _report(_rec(e_machine=999, parsed_attrs={"foo": "bar"}))
    host = _host(e_machines=frozenset({999}))
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "attrs")
    assert len(items) == 1
    assert items[0].compatible is None


def test_attrs_check_dedupes_identical_pairs() -> None:
    pkg = _report(
        _rec(e_machine=62, parsed_attrs={"isa_level": "v3"}),
        _rec(e_machine=62, parsed_attrs={"isa_level": "v3"}),
    )
    host = _host(e_machines=frozenset({62}), attrs={"62": {"isa_level": "v2"}})
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "attrs")
    assert len(items) == 1
    assert items[0].compatible is False


def test_attrs_check_satisfied() -> None:
    pkg = _report(
        _rec(e_machine=62, parsed_attrs={"isa_level": "v2"}),
        _rec(e_machine=62, parsed_attrs={"isa_level": "v2"}),
    )
    host = _host(e_machines=frozenset({62}), attrs={"62": {"isa_level": "v3"}})
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "attrs")
    assert len(items) == 1
    assert items[0].compatible is True


def test_attrs_distinct_pairs_each_item() -> None:
    pkg = _report(
        _rec(e_machine=62, parsed_attrs={"isa_level": "v2"}),
        _rec(e_machine=62, parsed_attrs={"isa_level": "v4"}),
    )
    host = _host(e_machines=frozenset({62}), attrs={"62": {"isa_level": "v3"}})
    report = check_host_compatibility(pkg, host)
    items = _items_of(report, "attrs")
    assert len(items) == 2
    seen_false = seen_true = False
    for i in items:
        assert i.compatible is not None
        if i.compatible:
            seen_true = True
        else:
            seen_false = True
    assert seen_true and seen_false
