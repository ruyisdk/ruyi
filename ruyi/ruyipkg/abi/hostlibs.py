"""Host shared-library resolution for ABI compatibility probing.

This models the host's search path *for installed packages*, not for the
ruyi process itself. Sources, in order: the glibc ld.so.cache, the musl
path file, and a fixed list of standard/triplet directories. It must
never consult os.environ["LD_LIBRARY_PATH"], never dlopen candidate
libraries, and never derive paths from __file__ or ruyi.__compiled__:
ruyi's own Nuitka-bundled libraries (onefile progcache) are unusable by
installed packages and must stay invisible here.
"""

from __future__ import annotations

import pathlib
import struct
from collections.abc import Sequence

_CACHE_MAGIC = b"glibc-ld.so.cache"
_CACHE_VERSION = b"1.1"
_FLAG_TYPE_MASK = 0x0003
_FLAG_ELF_LIBC6 = 0x0003
_FLAG_REQUIRED_MASK = 0xFF00

# Accepted FLAG_REQUIRED_MASK values per e_machine; absent = accept any.
_ARCH_FLAGS: dict[int, frozenset[int]] = {
    62: frozenset({0x0200}),  # FLAG_X8664_LIB64
    183: frozenset({0x0800}),  # FLAG_AARCH64_LIB64
    243: frozenset({0x0400, 0x0200}),  # RISC-V float-ABI soft / double
}

_TRIPLET_DIRS: dict[int, tuple[str, ...]] = {
    62: ("x86_64-linux-gnu",),
    183: ("aarch64-linux-gnu",),
    243: ("riscv64-linux-gnu",),
}

_DEFAULT_LIB_DIRS = ("/lib", "/usr/lib", "/usr/local/lib")


def parse_ld_so_cache(data: bytes) -> list[tuple[str, str, int]]:
    """Parse a glibc new-format cache into (soname, path, flags) tuples.

    Raises ValueError or struct.error on any format deviation; callers
    fall back to the directory walk.
    """
    header_len = 17 + 3 + 4 + 4 + 5 * 4
    if len(data) < header_len or not data.startswith(_CACHE_MAGIC):
        raise ValueError("not a glibc ld.so.cache")
    if data[17:20] != _CACHE_VERSION:
        raise ValueError("unsupported cache version")
    nlibs, _len_strings = struct.unpack_from("<II", data, 20)
    entries: list[tuple[str, str, int]] = []
    for i in range(nlibs):
        flags, key, value, _pad, _hwcap = struct.unpack_from(
            "<iIIIQ", data, header_len + 24 * i
        )

        def read_str(off: int) -> str:
            end = data.index(b"\x00", off)
            return data[off:end].decode("utf-8", "replace")

        entries.append((read_str(key), read_str(value), flags))
    return entries


class HostLibResolver:
    def __init__(
        self,
        e_machine: int,
        *,
        cache_path: pathlib.Path = pathlib.Path("/etc/ld.so.cache"),
        lib_dirs: Sequence[pathlib.Path] | None = None,
        musl_path_file: pathlib.Path | None = None,
    ) -> None:
        self._e_machine = e_machine
        self._index: dict[str, pathlib.Path] = {}
        entries: list[tuple[str, str, int]] = []
        try:
            entries = parse_ld_so_cache(cache_path.read_bytes())
        except (OSError, ValueError, struct.error):
            entries = []
        accepted = _ARCH_FLAGS.get(e_machine)
        for soname, path, flags in entries:
            if flags & _FLAG_TYPE_MASK != _FLAG_ELF_LIBC6:
                continue
            if accepted is not None and (flags & _FLAG_REQUIRED_MASK) not in accepted:
                continue
            self._index.setdefault(soname, pathlib.Path(path))
        dirs: list[pathlib.Path] = []
        if lib_dirs is not None:
            dirs = list(lib_dirs)
        else:
            musl = musl_path_file or pathlib.Path(
                f"/etc/ld-musl-{_musl_arch(e_machine)}.path"
            )
            try:
                dirs.extend(pathlib.Path(p) for p in musl.read_text().split(":") if p)
            except OSError:
                pass
            dirs.extend(pathlib.Path(d) for d in _DEFAULT_LIB_DIRS)
            for triplet in _TRIPLET_DIRS.get(e_machine, ()):
                dirs.append(pathlib.Path("/lib") / triplet)
                dirs.append(pathlib.Path("/usr/lib") / triplet)
        for d in dirs:
            try:
                for child in d.iterdir():
                    if ".so" not in child.name:
                        continue
                    if child.name not in self._index and child.is_file():
                        self._index[child.name] = child
            except OSError:
                continue

    def resolve(self, soname: str) -> pathlib.Path | None:
        return self._index.get(soname)

    def resolvable_sonames(self) -> frozenset[str]:
        return frozenset(self._index)


def _musl_arch(e_machine: int) -> str:
    return {62: "x86_64", 183: "aarch64", 243: "riscv64"}.get(e_machine, "unknown")
