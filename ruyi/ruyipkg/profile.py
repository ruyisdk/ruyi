import abc
from os import PathLike
from typing import Any, Callable, Iterable, NotRequired, TypedDict

from .pkg_manifest import EmulatorFlavor


class ProfileDeclType(TypedDict):
    name: str
    doc_uri: NotRequired[str]
    need_flavor: NotRequired[list[str]]
    # can contain arch-specific free-form str -> str mappings


class ArchProfilesDeclType(TypedDict):
    arch: str
    # rest are arch-specific free-form KVs


class ProfileDecl:
    def __init__(self, arch: str, decl: ProfileDeclType) -> None:
        self.arch = arch
        self.name = decl["name"]
        self.need_flavor: set[str] = set()
        self.doc_uri = decl.get("doc_uri")
        if "need_flavor" in decl:
            self.need_flavor = set(decl["need_flavor"])

    @abc.abstractmethod
    def get_common_flags(self) -> str:
        return ""

    @abc.abstractmethod
    def get_needed_emulator_pkg_flavors(
        self,
        flavor: EmulatorFlavor,
    ) -> set[str]:
        raise NotImplementedError

    @abc.abstractmethod
    def check_emulator_flavor(
        self,
        flavor: EmulatorFlavor,
        emulator_pkg_flavors: list[str] | None,
    ) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def get_env_config_for_emu_flavor(
        self,
        flavor: EmulatorFlavor,
        sysroot: PathLike[Any] | None,
    ) -> dict[str, str] | None:
        result: dict[str, str] = {}

        # right now this is the only supported flavor
        # if flavor == "qemu-linux-user" and sysroot is not None:
        if sysroot is not None:
            result["QEMU_LD_PREFIX"] = str(sysroot)

        return result


# should have been something like (str, T extends ArchProfilesDeclType) -> Iterable[U extends ProfileDecl]
# but apparently not supported: https://github.com/python/mypy/issues/7435
ArchProfileParser = Callable[[str, Any], Iterable[ProfileDecl]]

KNOWN_ARCHES: dict[str, ArchProfileParser] = {}


def register_arch_profile_parser(fn: ArchProfileParser, *arches: str) -> None:
    for a in arches:
        if a in KNOWN_ARCHES:
            raise ValueError(
                f"code bug: arch '{a}' is already registered as {KNOWN_ARCHES[a]}"
            )

        KNOWN_ARCHES[a] = fn


def parse_profiles(data: ArchProfilesDeclType) -> Iterable[ProfileDecl]:
    arch = data["arch"]
    try:
        arch_parser = KNOWN_ARCHES[arch]
    except KeyError:
        raise RuntimeError(f"arch '{arch}' is unknown to ruyi")

    return arch_parser(arch, data)


# register the built-in arches
from . import arch  # noqa: E402 # intentionally placed last for the side-effect

del arch
