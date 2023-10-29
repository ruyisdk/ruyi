from typing import NotRequired, TypedDict


class ProfileDeclType(TypedDict):
    name: str
    need_flavor: NotRequired[list[str]]
    # can contain arch-specific free-form str -> str mappings


class ArchProfilesDeclType(TypedDict):
    arch: str
    generic_opts: dict[str, str]
    profiles: list[ProfileDeclType]
    # can contain arch-specific free-form KVs
