import abc
from typing import Any, Callable, Iterable, NotRequired, TypedDict


class ProfileDeclType(TypedDict):
    name: str
    need_flavor: NotRequired[list[str]]
    # can contain arch-specific free-form str -> str mappings


class ArchProfilesDeclType(TypedDict):
    arch: str
    # rest are arch-specific free-form KVs


class ProfileDecl:
    def __init__(self, decl: ProfileDeclType) -> None:
        self.name = decl["name"]
        self.need_flavor: set[str] = set()
        if "need_flavor" in decl:
            self.need_flavor = set(decl["need_flavor"])

    @abc.abstractmethod
    def get_common_flags(self) -> str:
        return ""


# should have been something like (T extends ArchProfilesDeclType) -> Iterable[U extends ProfileDecl]
# but apparently not supported: https://github.com/python/mypy/issues/7435
ArchProfileParser = Callable[[Any], Iterable[ProfileDecl]]

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

    return arch_parser(data)


# put this last: register the built-in arches
from . import arch
