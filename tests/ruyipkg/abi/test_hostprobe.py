from __future__ import annotations

import pathlib

from pytest import MonkeyPatch

from ruyi.log import RuyiLogger
from ruyi.ruyipkg import abi as abi_pkg
from ruyi.ruyipkg.abi import ABISource, hostprobe
from ruyi.ruyipkg.abi.aggregate import build_summary
from ruyi.ruyipkg.abi.hostlibs import ResolvesHostLibs
from ruyi.ruyipkg.abi.hostprobe import HostABIProber, HostABIReport
from ruyi.ruyipkg.abi.model import ABIReport, ElfABIRecord, ElfType, VersionNeed
from ruyi.ruyipkg.abi.sources import _PathsSource


def _manifest(
    *,
    needed: tuple[str, ...] = (),
    version_needs: tuple[VersionNeed, ...] = (),
    interpreters: tuple[str, ...] = (),
    e_machines: tuple[int, ...] = (62,),
    parsed: tuple[tuple[int, dict[str, str | int | bool]], ...] = (
        (62, {"isa_level": "v2"}),
    ),
) -> ABIReport:
    records = tuple(
        ElfABIRecord(
            paths=(f"bin/{i}",),
            sha256=f"{i:064d}",
            e_machine=m,
            elf_class=64,
            endianness="little",
            elf_type=ElfType.EXEC,
            is_dynamic=True,
            interpreter=interp,
            soname=None,
            needed=needed,
            version_needs=version_needs,
            version_defs=(),
            needs_unversioned=False,
            gnu_properties=(),
            elf_attributes=(),
            parsed_attrs=dict(attrs),
        )
        for i, ((m, attrs), interp) in enumerate(
            zip(parsed, interpreters or [None] * len(parsed))
        )
    )
    return ABIReport(
        records=records,
        summary=build_summary(records, file_count=len(records), excluded_count=0),
        errors=(),
    )


def _empty_report() -> ABIReport:
    return ABIReport(
        records=(),
        summary=build_summary((), file_count=0, excluded_count=0),
        errors=(),
    )


def _empty_host_report() -> HostABIReport:
    return HostABIReport(
        e_machines=frozenset(),
        elf_class=0,
        endianness="",
        resolvable_sonames=frozenset(),
        providers=None,
        interpreter_paths_present=frozenset(),
        attrs={},
    )


class _FakeResolver(ResolvesHostLibs):
    def __init__(self, mapping: dict[str, pathlib.Path]) -> None:
        self._mapping = mapping

    def resolve(self, soname: str) -> pathlib.Path | None:
        return self._mapping.get(soname)

    def resolvable_sonames(self) -> frozenset[str]:
        return frozenset(self._mapping.keys())


def _stub_interpreters(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(hostprobe, "get_interpreter", lambda _m: None)


def test_scans_only_provider_paths(monkeypatch: MonkeyPatch) -> None:
    scanned: list[list[str]] = []

    def fake_scan(source: _PathsSource, *, logger: RuyiLogger) -> ABIReport:
        scanned.append([str(p) for p in source._paths])
        return _empty_report()

    monkeypatch.setattr(abi_pkg, "scan_source", fake_scan)
    _stub_interpreters(monkeypatch)

    manifest = _manifest(
        needed=("liba.so",),
        version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.34",)),),
    )
    prober = HostABIProber(
        resolver=_FakeResolver(
            {
                "liba.so": pathlib.Path("/lib/liba.so"),
                "libc.so.6": pathlib.Path("/lib/libc.so.6"),
            },
        ),
        host_arch="x86_64",
    )
    report = prober.probe(manifest)

    assert report.resolvable_sonames == frozenset({"liba.so"})
    assert scanned == [["/lib/libc.so.6"]]


def test_dangling_provider_degrades_to_none(monkeypatch: MonkeyPatch) -> None:
    def boom(source: ABISource, *, logger: RuyiLogger) -> ABIReport:
        raise OSError("dangling symlink")

    monkeypatch.setattr(abi_pkg, "scan_source", boom)
    _stub_interpreters(monkeypatch)

    manifest = _manifest(version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.34",)),))
    prober = HostABIProber(
        resolver=_FakeResolver({"libc.so.6": pathlib.Path("/lib/libc.so.6")}),
        host_arch="x86_64",
    )
    report = prober.probe(manifest)

    assert report.providers is None


def test_interpreter_paths_present(monkeypatch: MonkeyPatch) -> None:
    _stub_interpreters(monkeypatch)
    interp = "/lib/ld-linux-x86-64.so.2"

    manifest = _manifest(interpreters=(interp,))
    prober = HostABIProber(
        resolver=_FakeResolver({}),
        exists=lambda p: p == interp,
        host_arch="x86_64",
    )
    report = prober.probe(manifest)

    assert report.interpreter_paths_present == frozenset({interp})


def test_host_attrs_keyed_by_e_machine(monkeypatch: MonkeyPatch) -> None:
    class FakeInterp:
        def host_attrs(self) -> dict[str, str | int | bool]:
            return {"isa_level": "v3"}

    monkeypatch.setattr(
        hostprobe,
        "get_interpreter",
        lambda m: FakeInterp() if m == 62 else None,
    )

    manifest = _manifest()
    prober = HostABIProber(resolver=_FakeResolver({}), host_arch="x86_64")
    report = prober.probe(manifest)

    assert report.attrs == {"62": {"isa_level": "v3"}}


def test_unknown_host_arch(monkeypatch: MonkeyPatch) -> None:
    _stub_interpreters(monkeypatch)
    prober = HostABIProber(resolver=_FakeResolver({}), host_arch="foo")

    report = prober.probe(_manifest())

    assert report.e_machines == frozenset()
    assert report.elf_class == 64
    assert report.endianness == "little"


def test_probe_rebuilds_the_owned_resolver(monkeypatch: MonkeyPatch) -> None:
    created: list[_FakeResolver] = []

    def make_resolver(e_machine: int) -> _FakeResolver:
        r = _FakeResolver({})
        created.append(r)
        return r

    monkeypatch.setattr(hostprobe, "HostLibResolver", make_resolver)
    _stub_interpreters(monkeypatch)

    prober = HostABIProber(host_arch="x86_64", exists=lambda _p: False)
    manifest = _manifest()
    prober.probe(manifest)
    prober.probe(manifest)

    # A reused prober must not keep an index from before the host changed.
    assert len(created) == 2
