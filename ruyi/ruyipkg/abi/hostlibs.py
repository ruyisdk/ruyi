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

from collections.abc import Sequence
import pathlib
import struct
from typing import NamedTuple, Protocol

_CACHE_MAGIC = b"glibc-ld.so.cache"
_CACHE_VERSION = b"1.1"
_FLAG_TYPE_MASK = 0x0003
_FLAG_ELF_LIBC6 = 0x0003
_FLAG_REQUIRED_MASK = 0xFF00

_FLAG_RISCV_FLOAT_ABI_SOFT = 0x0F00
_FLAG_RISCV_FLOAT_ABI_DOUBLE = 0x1000

_EM_RISCV = 243
_EF_RISCV_FLOAT_ABI = 0x6
_EF_RISCV_FLOAT_ABI_SOFT = 0x0
_EF_RISCV_FLOAT_ABI_DOUBLE = 0x4

# Accepted FLAG_REQUIRED_MASK values per e_machine; absent = accept any.
_ARCH_FLAGS: dict[int, frozenset[int]] = {
    62: frozenset({0x0300}),  # FLAG_X8664_LIB64
    183: frozenset({0x0A00}),  # FLAG_AARCH64_LIB64
    243: frozenset({_FLAG_RISCV_FLOAT_ABI_SOFT, _FLAG_RISCV_FLOAT_ABI_DOUBLE}),
}

_RISCV_FLOAT_ABI_FLAGS: dict[str, frozenset[int]] = {
    "soft": frozenset({_FLAG_RISCV_FLOAT_ABI_SOFT}),
    "double": frozenset({_FLAG_RISCV_FLOAT_ABI_DOUBLE}),
}

# ELF class of the native libraries for each supported e_machine.  Only these
# architectures have their candidate files cross-checked, matching the way the
# loader's open_verify() rejects a library of a foreign class or machine.
_ARCH_ELF_CLASS: dict[int, int] = {
    62: 64,
    183: 64,
    243: 64,
}

_TRIPLET_DIRS: dict[int, tuple[str, ...]] = {
    62: ("x86_64-linux-gnu",),
    183: ("aarch64-linux-gnu",),
    243: ("riscv64-linux-gnu",),
}

_DEFAULT_LIB_DIRS = ("/lib", "/usr/lib", "/usr/local/lib")

# Architectures whose 64-bit libraries may live in dedicated directories that
# coexist with 32-bit ones, so they must be searched before the generic list.
_LIB64_ARCHES = frozenset({62, 183, 243})  # x86-64, AArch64, RISC-V
_LIB64_DIRS = ("/lib64", "/usr/lib64")


def _system_lib_dirs(e_machine: int) -> tuple[pathlib.Path, ...]:
    dirs: list[pathlib.Path] = []
    if e_machine in _LIB64_ARCHES:
        dirs.extend(pathlib.Path(d) for d in _LIB64_DIRS)
    dirs.extend(pathlib.Path(d) for d in _DEFAULT_LIB_DIRS)
    for triplet in _TRIPLET_DIRS.get(e_machine, ()):
        dirs.append(pathlib.Path("/lib") / triplet)
        dirs.append(pathlib.Path("/usr/lib") / triplet)
    return tuple(dirs)


class CacheEntry(NamedTuple):
    soname: str
    path: str
    flags: int
    hwcap: int


def parse_ld_so_cache(data: bytes) -> list[CacheEntry]:
    """Parse a glibc new-format cache into entries.

    Raises ValueError or struct.error on any format deviation; callers
    fall back to the directory walk.
    """
    header_len = 17 + 3 + 4 + 4 + 5 * 4
    if len(data) < header_len or not data.startswith(_CACHE_MAGIC):
        raise ValueError("not a glibc ld.so.cache")
    if data[17:20] != _CACHE_VERSION:
        raise ValueError("unsupported cache version")
    nlibs, _len_strings = struct.unpack_from("<II", data, 20)
    entries: list[CacheEntry] = []
    for i in range(nlibs):
        flags, key, value, _pad, hwcap = struct.unpack_from(
            "<iIIIQ", data, header_len + 24 * i
        )

        def read_str(off: int) -> str:
            end = data.index(b"\x00", off)
            return data[off:end].decode("utf-8", "replace")

        entries.append(CacheEntry(read_str(key), read_str(value), flags, hwcap))
    return entries


class ResolvesHostLibs(Protocol):
    def resolve(self, soname: str) -> pathlib.Path | None: ...

    def resolvable_sonames(self) -> frozenset[str]: ...


class HostLibResolver(ResolvesHostLibs):
    """Resolve installed libraries, querying only the requested sonames.

    The ld.so.cache is parsed eagerly, but the configured library directories
    are consulted per soname from resolve(), so a manifest without
    dependencies does not cause a directory walk.
    """

    def __init__(
        self,
        e_machine: int,
        *,
        cache_path: pathlib.Path = pathlib.Path("/etc/ld.so.cache"),
        lib_dirs: Sequence[pathlib.Path] | None = None,
        musl_path_file: pathlib.Path | None = None,
        riscv_float_abi: str | None = None,
    ) -> None:
        self._e_machine = e_machine
        self._elf_class = _ARCH_ELF_CLASS.get(e_machine, 0)
        self._candidates: dict[str, list[pathlib.Path]] = {}
        self._resolved: dict[str, pathlib.Path | None] = {}
        entries: list[CacheEntry] = []
        try:
            entries = parse_ld_so_cache(cache_path.read_bytes())
        except (OSError, ValueError, struct.error):
            entries = []
        accepted = _ARCH_FLAGS.get(e_machine)
        if e_machine == _EM_RISCV:
            # The cache only carries entries for the float ABI ldconfig was
            # built for, so narrow the accepted flags to the running host's.
            abi = riscv_float_abi or _native_riscv_float_abi()
            if abi in _RISCV_FLOAT_ABI_FLAGS:
                accepted = _RISCV_FLOAT_ABI_FLAGS[abi]
        for entry in entries:
            if entry.hwcap != 0:
                # In this cache format the field is either legacy hwcap bits
                # (removed from glibc in 2.37) or an index into the
                # glibc-hwcaps extension, which we do not decode. Ignore the
                # entry instead of scanning a library the loader may skip.
                continue
            if entry.flags & _FLAG_TYPE_MASK != _FLAG_ELF_LIBC6:
                continue
            if (
                accepted is not None
                and (entry.flags & _FLAG_REQUIRED_MASK) not in accepted
            ):
                continue
            self._add_candidate(entry.soname, pathlib.Path(entry.path))
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
            dirs.extend(_system_lib_dirs(e_machine))
        self._lib_dirs = tuple(dirs)

    def _add_candidate(self, soname: str, path: pathlib.Path) -> None:
        candidates = self._candidates.setdefault(soname, [])
        if path not in candidates:
            candidates.append(path)

    def _index_dir_candidate(self, soname: str) -> None:
        """Add the requested soname from the library directories, if present.

        Looking the name up directly avoids enumerating entire directories
        for libraries the manifest never asks about, and also covers sonames
        that do not contain ``.so``.
        """
        if not soname or pathlib.PurePath(soname).name != soname:
            # A DT_NEEDED entry containing a slash is a path, not an
            # installed soname; never join it onto a library directory.
            return
        for d in self._lib_dirs:
            candidate = d / soname
            try:
                if candidate.is_file():
                    self._add_candidate(soname, candidate)
            except OSError:
                continue

    def resolve(self, soname: str) -> pathlib.Path | None:
        if soname not in self._resolved:
            self._index_dir_candidate(soname)
            self._resolved[soname] = next(
                (
                    path
                    for path in self._candidates.get(soname, ())
                    if self._candidate_matches(path)
                ),
                None,
            )
        return self._resolved[soname]

    def resolvable_sonames(self) -> frozenset[str]:
        return frozenset(s for s in self._candidates if self.resolve(s) is not None)

    def _candidate_matches(self, path: pathlib.Path) -> bool:
        """Reject candidates the host's loader would not accept.

        This mirrors the class and machine checks of open_verify(): a stale
        cache entry or a wrong-class file in a multilib directory must not be
        mistaken for a usable provider.
        """
        if self._elf_class == 0:
            return True
        try:
            with path.open("rb") as fp:
                head = fp.read(20)
        except OSError:
            return False
        if len(head) < 20 or head[:4] != b"\x7fELF":
            return False
        expected_class = 1 if self._elf_class == 32 else 2
        if head[4] != expected_class or head[5] != 1:
            return False
        return int.from_bytes(head[18:20], "little") == self._e_machine


def _musl_arch(e_machine: int) -> str:
    return {62: "x86_64", 183: "aarch64", 243: "riscv64"}.get(e_machine, "unknown")


def _native_riscv_float_abi() -> str | None:
    """Return the running executable's RISC-V float ABI, if determinable.

    The cache contains entries for the float ABI of the ldconfig that wrote
    it, which on a native host is the ABI the running program was built for.
    Read it from /proc/self/exe's e_flags, and give up on any other machine.
    """
    try:
        with open("/proc/self/exe", "rb") as fp:
            head = fp.read(52)
    except OSError:
        return None
    if len(head) < 52 or head[:4] != b"\x7fELF":
        return None
    endian = "<" if head[5] == 1 else ">"
    (machine,) = struct.unpack_from(endian + "H", head, 18)
    if machine != _EM_RISCV:
        return None
    flags_offset = 36 if head[4] == 1 else 48
    (flags,) = struct.unpack_from(endian + "I", head, flags_offset)
    abi = flags & _EF_RISCV_FLOAT_ABI
    if abi == _EF_RISCV_FLOAT_ABI_SOFT:
        return "soft"
    if abi == _EF_RISCV_FLOAT_ABI_DOUBLE:
        return "double"
    return None
