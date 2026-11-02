import pathlib
from typing import Any

import pytest
from pytest import MonkeyPatch

import ruyi.ruyipkg.host_compat as host_compat
from ruyi.ruyipkg.abi import (
    ABIReport,
    ElfABIRecord,
    ElfType,
    dump_abi_report_toml,
)
from ruyi.ruyipkg.abi.aggregate import build_summary
from ruyi.ruyipkg.abi.hostprobe import HostABIReport
from ruyi.ruyipkg.host import RuyiHost
from ruyi.ruyipkg.host_compat import (
    HostCompatChecker,
    HostCompatProblem,
    HostCompatStatus,
    PackageHostCompat,
    format_problem,
)
from ruyi.ruyipkg.pkg_manifest import (
    BoundPackageManifest,
    InputPackageManifestType,
)


@pytest.fixture(autouse=True)
def _identity_gettext(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(host_compat, "_", lambda s: s)


def test_status_markup() -> None:
    assert HostCompatStatus.Unchecked.as_rich_markup() == "unchecked"
    assert HostCompatStatus.NoABIInfo.as_rich_markup() == "[dim]no ABI info[/]"
    assert (
        HostCompatStatus.LikelyCompatible.as_rich_markup()
        == "[green]likely compatible[/]"
    )
    assert (
        HostCompatStatus.LikelyIncompatible.as_rich_markup()
        == "[red]likely incompatible[/]"
    )
    assert (
        HostCompatStatus.CompatibilityUnknown.as_rich_markup()
        == "[yellow]compatibility unknown[/]"
    )


def test_package_host_compat_to_porcelain() -> None:
    compat = PackageHostCompat(
        HostCompatStatus.LikelyIncompatible,
        problems=(
            HostCompatProblem(
                "e-machine",
                False,
                "package targets e_machine(s) {want}, host is {got}",
                {"want": [243], "got": [62]},
            ),
        ),
        sidecars=(pathlib.Path("/repo/_abi/pkg.tar.abi.toml"),),
    )

    assert compat.to_porcelain() == {
        "status": "likely-incompatible",
        "problems": [
            {
                "check": "e-machine",
                "compatible": False,
                "msgid": "package targets e_machine(s) {want}, host is {got}",
                "params": {"want": [243], "got": [62]},
            }
        ],
    }


def test_format_problem() -> None:
    problem = HostCompatProblem(
        "soname",
        None,
        "could not locate shared library {soname} on this host",
        {"soname": "libc.so.6"},
    )

    assert (
        format_problem(problem)
        == "soname: could not locate shared library libc.so.6 on this host"
    )


class _FakeLogger:
    def __init__(self) -> None:
        self.warnings: list[str] = []
        self.debugs: list[str] = []

    def W(self, message: str = "", *args: Any, **kwargs: Any) -> None:
        self.warnings.append(message)

    def D(self, message: str = "", *args: Any, **kwargs: Any) -> None:
        self.debugs.append(message)


class _FakeRepo:
    repo_id = "test-repo"
    messages = None

    def __init__(self, root: pathlib.Path) -> None:
        self.root = str(root)


class _FakeProber:
    def __init__(self, report: HostABIReport) -> None:
        self._report = report
        self.manifests: list[ABIReport] = []

    def probe(self, manifest: ABIReport) -> HostABIReport:
        self.manifests.append(manifest)
        return self._report


class _FailingProber:
    def probe(self, manifest: ABIReport) -> HostABIReport:
        raise RuntimeError("probe failed")


@pytest.fixture(autouse=True)
def _native_host(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        host_compat,
        "get_native_host",
        lambda: RuyiHost("linux", "x86_64"),
    )


def _record(e_machine: int = 62, sha: str = "0" * 64) -> ElfABIRecord:
    return ElfABIRecord(
        paths=("bin/x",),
        sha256=sha,
        e_machine=e_machine,
        elf_class=64,
        endianness="little",
        elf_type=ElfType.DYN,
        is_dynamic=True,
        interpreter=None,
        soname=None,
        needed=(),
        version_needs=(),
        version_defs=(),
        needs_unversioned=False,
        gnu_properties=(),
        elf_attributes=(),
        parsed_attrs={},
    )


def _report(*records: ElfABIRecord) -> ABIReport:
    return ABIReport(
        records=records,
        summary=build_summary(
            records,
            file_count=len(records),
            excluded_count=0,
        ),
        errors=(),
    )


def _host(e_machines: tuple[int, ...] = (62,)) -> HostABIReport:
    return HostABIReport(
        e_machines=frozenset(e_machines),
        elf_class=64,
        endianness="little",
        resolvable_sonames=frozenset(),
        providers=None,
        interpreter_paths_present=frozenset(),
        attrs={},
    )


def _manifest(
    root: pathlib.Path,
    *,
    distfiles: tuple[str, ...] = ("pkg.tar.zst",),
    host: str = "x86_64",
) -> BoundPackageManifest:
    data: InputPackageManifestType = {
        "format": "v1",
        "metadata": {
            "desc": "test package",
            "vendor": {"name": "Acme", "eula": None},
        },
        "distfiles": [
            {
                "name": name,
                "size": 1,
                "checksums": {"sha256": "0" * 64},
            }
            for name in distfiles
        ],
        "binary": [{"host": host, "distfiles": list(distfiles)}],
    }
    return BoundPackageManifest(
        "dev-tools",
        "sample-cli",
        "1.0.0",
        data,
        _FakeRepo(root),  # type: ignore[arg-type]
    )


def _write_sidecar(
    root: pathlib.Path,
    distfile_name: str,
    report: ABIReport,
) -> pathlib.Path:
    sidecar = (
        root
        / "packages"
        / "dev-tools"
        / "sample-cli"
        / "_abi"
        / f"{distfile_name}.abi.toml"
    )
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(dump_abi_report_toml(report), encoding="utf-8")
    return sidecar


def test_checker_is_unchecked_when_probing_is_disabled(
    tmp_path: pathlib.Path,
) -> None:
    prober = _FakeProber(_host())
    checker = HostCompatChecker(logger=_FakeLogger(), prober=prober)  # type: ignore[arg-type]

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=False,
    )

    assert compat.status is HostCompatStatus.Unchecked
    assert compat.problems == ()
    assert prober.manifests == []


def test_checker_is_unchecked_for_non_native_host(tmp_path: pathlib.Path) -> None:
    prober = _FakeProber(_host())
    checker = HostCompatChecker(logger=_FakeLogger(), prober=prober)  # type: ignore[arg-type]

    compat = checker.check(
        _manifest(tmp_path),
        "riscv64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.Unchecked
    assert prober.manifests == []


def test_checker_reports_no_abi_info_without_sidecar(tmp_path: pathlib.Path) -> None:
    checker = HostCompatChecker(
        logger=_FakeLogger(),  # type: ignore[arg-type]
        prober=_FakeProber(_host()),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.NoABIInfo
    assert compat.problems == ()


def test_checker_treats_empty_sidecar_as_no_abi_info(
    tmp_path: pathlib.Path,
) -> None:
    _write_sidecar(tmp_path, "pkg.tar.zst", _report())
    logger = _FakeLogger()
    prober = _FakeProber(_host())
    checker = HostCompatChecker(
        logger=logger,  # type: ignore[arg-type]
        prober=prober,  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.NoABIInfo
    assert prober.manifests == []
    assert logger.warnings == []


def test_checker_reports_likely_compatible(tmp_path: pathlib.Path) -> None:
    _write_sidecar(tmp_path, "pkg.tar.zst", _report(_record()))
    checker = HostCompatChecker(
        logger=_FakeLogger(),  # type: ignore[arg-type]
        prober=_FakeProber(_host()),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.LikelyCompatible
    assert compat.problems == ()


def test_checker_reports_likely_incompatible(tmp_path: pathlib.Path) -> None:
    _write_sidecar(tmp_path, "pkg.tar.zst", _report(_record(243)))
    checker = HostCompatChecker(
        logger=_FakeLogger(),  # type: ignore[arg-type]
        prober=_FakeProber(_host()),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.LikelyIncompatible
    assert [p.check for p in compat.problems] == ["e-machine"]
    assert compat.problems[0].compatible is False


def test_checker_reports_unknown_when_the_probe_is_undetermined(
    tmp_path: pathlib.Path,
) -> None:
    _write_sidecar(tmp_path, "pkg.tar.zst", _report(_record()))
    checker = HostCompatChecker(
        logger=_FakeLogger(),  # type: ignore[arg-type]
        prober=_FakeProber(_host(e_machines=())),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.CompatibilityUnknown
    assert [p.check for p in compat.problems] == ["e-machine"]
    assert compat.problems[0].compatible is None


def test_checker_reports_unknown_for_partial_sidecar_coverage(
    tmp_path: pathlib.Path,
) -> None:
    _write_sidecar(tmp_path, "a.tar.zst", _report(_record()))
    checker = HostCompatChecker(
        logger=_FakeLogger(),  # type: ignore[arg-type]
        prober=_FakeProber(_host()),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path, distfiles=("a.tar.zst", "b.tar.zst")),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.CompatibilityUnknown


def test_checker_degrades_on_malformed_sidecar(tmp_path: pathlib.Path) -> None:
    sidecar = (
        tmp_path
        / "packages"
        / "dev-tools"
        / "sample-cli"
        / "_abi"
        / "pkg.tar.zst.abi.toml"
    )
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("not toml", encoding="utf-8")
    logger = _FakeLogger()
    checker = HostCompatChecker(
        logger=logger,  # type: ignore[arg-type]
        prober=_FakeProber(_host()),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.NoABIInfo
    assert len(logger.warnings) == 1


def test_checker_degrades_on_oversized_sidecar(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    _write_sidecar(tmp_path, "pkg.tar.zst", _report())
    monkeypatch.setattr(host_compat, "DEFAULT_MAX_SIDECAR_BYTES", 3)
    logger = _FakeLogger()
    checker = HostCompatChecker(
        logger=logger,  # type: ignore[arg-type]
        prober=_FakeProber(_host()),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.NoABIInfo
    assert len(logger.warnings) == 1


def test_checker_merges_multiple_sidecars_before_probing(
    tmp_path: pathlib.Path,
) -> None:
    _write_sidecar(tmp_path, "a.tar.zst", _report(_record(sha="1" * 64)))
    _write_sidecar(tmp_path, "b.tar.zst", _report(_record(sha="2" * 64)))
    prober = _FakeProber(_host())
    checker = HostCompatChecker(logger=_FakeLogger(), prober=prober)  # type: ignore[arg-type]

    compat = checker.check(
        _manifest(tmp_path, distfiles=("a.tar.zst", "b.tar.zst")),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.LikelyCompatible
    assert len(prober.manifests) == 1
    assert len(prober.manifests[0].records) == 2


def test_checker_degrades_on_type_invalid_sidecar(tmp_path: pathlib.Path) -> None:
    sidecar = _write_sidecar(tmp_path, "pkg.tar.zst", _report())
    text = sidecar.read_text(encoding="utf-8")
    sidecar.write_text(
        text.replace("file_count = 0", 'file_count = "not-an-int"'),
        encoding="utf-8",
    )
    logger = _FakeLogger()
    checker = HostCompatChecker(
        logger=logger,  # type: ignore[arg-type]
        prober=_FakeProber(_host()),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.NoABIInfo
    assert compat.problems == ()
    assert len(logger.warnings) == 1


def test_checker_drops_invalid_non_empty_sidecar_before_caching(
    tmp_path: pathlib.Path,
) -> None:
    sidecar = _write_sidecar(tmp_path, "pkg.tar.zst", _report(_record()))
    text = sidecar.read_text(encoding="utf-8")
    sidecar.write_text(
        text.replace("file_count = 1", 'file_count = "bad"'),
        encoding="utf-8",
    )
    logger = _FakeLogger()
    prober = _FakeProber(_host())
    checker = HostCompatChecker(
        logger=logger,  # type: ignore[arg-type]
        prober=prober,  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.NoABIInfo
    assert len(logger.warnings) == 1
    assert prober.manifests == []

    again = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert again.status is HostCompatStatus.NoABIInfo
    assert len(logger.warnings) == 1
    assert prober.manifests == []


def test_checker_degrades_when_probing_raises(tmp_path: pathlib.Path) -> None:
    _write_sidecar(tmp_path, "pkg.tar.zst", _report(_record()))
    checker = HostCompatChecker(
        logger=_FakeLogger(),  # type: ignore[arg-type]
        prober=_FailingProber(),  # type: ignore[arg-type]
    )

    compat = checker.check(
        _manifest(tmp_path),
        "x86_64",
        allow_probing=True,
    )

    assert compat.status is HostCompatStatus.CompatibilityUnknown
    assert compat.problems == ()
