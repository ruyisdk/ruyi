from os import PathLike
from typing import Any, TypedDict


class ConfiguredTargetTuple(TypedDict):
    target: str
    toolchain_root: PathLike[Any]
    toolchain_sysroot: PathLike[Any] | None
    toolchain_flags: str
    binutils_flavor: str
    cc_flavor: str
    gcc_install_dir: PathLike[Any] | None
