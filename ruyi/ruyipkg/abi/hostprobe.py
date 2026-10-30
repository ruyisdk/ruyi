"""Focused host ABI probing driven by a package ABI manifest.

The manifest is the query plan: only the sonames, interpreter paths, and
e_machines it mentions cause any host I/O. Probe state is memoized for the
duration of one probe and never persisted to disk, so users may freely update
their systems without anything our side becoming stale.
"""

from __future__ import annotations

import pathlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from ...log import RuyiLogger
from ..host import get_native_host
from .hostlibs import HostLibResolver, ResolvesHostLibs
from .interp import ArchMetadata, get_interpreter, recognize_arch_by_uname
from .model import ABIReport


@dataclass(frozen=True)
class HostABIReport:
    e_machines: frozenset[int]  # empty = unknown host arch
    elf_class: int  # 0 = unknown
    endianness: str  # "" = unknown
    resolvable_sonames: frozenset[str]
    providers: ABIReport | None  # None = provider scan failed
    interpreter_paths_present: frozenset[str]
    attrs: Mapping[str, Mapping[str, object]]  # str(e_machine) -> host attrs


class HostABIProber:
    """Probe host facts for one manifest.

    The resolver is rebuilt for each probe so libraries installed or removed
    between calls are taken into account; facts are memoized only while a
    single probe runs.
    """

    def __init__(
        self,
        *,
        resolver: ResolvesHostLibs | None = None,
        exists: Callable[[str], bool] = lambda p: pathlib.Path(p).exists(),
        host_arch: str | None = None,
        logger: RuyiLogger | None = None,
    ) -> None:
        am = recognize_arch_by_uname(host_arch) or ArchMetadata(0, 64, "little")
        self._arch_metadata = am
        self._host_arch = host_arch or get_native_host().arch
        self._owns_resolver = resolver is None
        self._resolver: ResolvesHostLibs | None = resolver
        self._exists = exists
        self._logger = logger

    @property
    def e_machine(self) -> int:
        return self._arch_metadata.elf_machine

    def probe(self, manifest: ABIReport) -> HostABIReport:
        if self._owns_resolver:
            self._resolver = HostLibResolver(self._arch_metadata.elf_machine)
        assert self._resolver is not None

        interpreters = {
            r.interpreter for r in manifest.records if r.interpreter is not None
        }
        present = frozenset(p for p in interpreters if self._exists(p))

        resolvable = frozenset(
            s for s in manifest.summary.needed if self._resolver.resolve(s) is not None
        )

        provider_paths = sorted(
            {
                str(p)
                for vn in manifest.summary.version_needs
                if (p := self._resolver.resolve(vn.soname)) is not None
            }
        )
        providers: ABIReport | None = None
        try:
            from . import scan_source
            from .sources import ABISource

            providers = scan_source(
                ABISource.from_paths(provider_paths),
                logger=self._logger,
            )
        except Exception as exc:  # noqa: BLE001 - degrade, never raise
            if self._logger is not None:
                self._logger.D(f"provider library ABI scan failed: {exc}")
            providers = None

        attrs: dict[str, Mapping[str, object]] = {}
        for m in manifest.summary.e_machines:
            interp = get_interpreter(m)
            if interp is None:
                continue
            try:
                attrs[str(m)] = interp.host_attrs()
            except Exception as exc:  # noqa: BLE001
                if self._logger is not None:
                    self._logger.D(
                        f"host attribute probe for e_machine {m} failed: {exc}"
                    )

        return HostABIReport(
            e_machines=frozenset({self.e_machine}) if self.e_machine else frozenset(),
            elf_class=self._arch_metadata.bitness,
            endianness=self._arch_metadata.endianness,
            resolvable_sonames=resolvable,
            providers=providers,
            interpreter_paths_present=present,
            attrs=attrs,
        )
