import pathlib
import struct

import pytest
from pytest import MonkeyPatch

from ruyi.ruyipkg.abi.hostlibs import HostLibResolver, _system_lib_dirs

_CACHE_MAGIC = b"glibc-ld.so.cache"
_CACHE_VERSION = b"1.1"
_FLAG_ELF_LIBC6 = 0x0003
_FLAG_X8664_LIB64 = 0x0300
_FLAG_AARCH64_LIB64 = 0x0A00
_FLAG_RISCV_FLOAT_ABI_DOUBLE = 0x1000


def _elf_header(e_machine: int, elf_class: int = 2, data: int = 1) -> bytes:
    """Minimal ELF header prefix, enough to identify class and machine."""
    ident = b"\x7fELF" + bytes([elf_class, data, 1, 0]) + b"\x00" * 8
    return ident + struct.pack("<HH", 1, e_machine)


def build_cache(entries: list[tuple[str, str, int]]) -> bytes:
    """entries: (soname, path, flags); glibc new-format layout."""
    header_len = 17 + 3 + 4 + 4 + 5 * 4
    entry_len = 24
    strtab = bytearray()
    offs: dict[str, int] = {}

    def intern(s: str) -> int:
        if s not in offs:
            offs[s] = header_len + entry_len * len(entries) + len(strtab)
            strtab.extend(s.encode())
            strtab.extend(b"\x00")
        return offs[s]

    ents = b"".join(
        struct.pack("<iIIIQ", flags, intern(k), intern(v), 0, 0)
        for k, v, flags in entries
    )
    header = (
        _CACHE_MAGIC
        + _CACHE_VERSION
        + struct.pack("<II", len(entries), len(strtab))
        + b"\x00" * 20
    )
    return header + ents + bytes(strtab)


def test_resolve_from_cache(tmp_path: pathlib.Path) -> None:
    lib = tmp_path / "x86_64-linux-gnu" / "libc.so.6"
    lib.parent.mkdir()
    lib.write_bytes(_elf_header(62))
    cache = build_cache(
        [
            ("libc.so.6", str(lib), _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64),
            (
                "libc.so.6",
                str(tmp_path / "lib32" / "libc.so.6"),
                _FLAG_ELF_LIBC6,
            ),  # 32-bit: filtered out
        ]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert r.resolve("libc.so.6") == lib


@pytest.mark.parametrize(
    ("e_machine", "arch_flag"),
    [
        (183, _FLAG_AARCH64_LIB64),
        (243, _FLAG_RISCV_FLOAT_ABI_DOUBLE),
    ],
)
def test_resolve_from_cache_for_other_arches(
    tmp_path: pathlib.Path, e_machine: int, arch_flag: int
) -> None:
    lib = tmp_path / "libc.so.6"
    lib.write_bytes(_elf_header(e_machine))
    cache = build_cache([("libc.so.6", str(lib), _FLAG_ELF_LIBC6 | arch_flag)])
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(e_machine, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert r.resolve("libc.so.6") == lib


def test_multilib_cache_entry_filtered_by_flags(tmp_path: pathlib.Path) -> None:
    # A foreign-class (32-bit) entry alone must never be offered as provider.
    lib = tmp_path / "i386-linux-gnu" / "libc.so.6"
    lib.parent.mkdir()
    lib.write_bytes(_elf_header(3, elf_class=1))
    cache = build_cache(
        [
            ("libc.so.6", str(lib), _FLAG_ELF_LIBC6),
        ]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert r.resolve("libc.so.6") is None
    assert "libc.so.6" not in r.resolvable_sonames()


def test_system_lib_dirs_prefer_64_bit_on_64_bit_arches() -> None:
    # On multilib hosts /lib and /usr/lib hold the 32-bit libraries, so the
    # 64-bit directories must be searched first.
    for e_machine in (62, 183, 243):
        dirs = _system_lib_dirs(e_machine)
        assert dirs.index(pathlib.Path("/lib64")) < dirs.index(pathlib.Path("/lib"))
        assert dirs.index(pathlib.Path("/usr/lib64")) < dirs.index(
            pathlib.Path("/usr/lib")
        )


def test_system_lib_dirs_skip_lib64_on_32_bit_arch() -> None:
    assert pathlib.Path("/lib64") not in _system_lib_dirs(3)


def test_malformed_cache_falls_back_to_dirs(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "ld.so.cache"
    bad.write_bytes(b"glibc-ld.so.cache1.1" + b"\x00" * 8)  # truncated
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "libm.so.6").write_bytes(b"")
    r = HostLibResolver(62, cache_path=bad, lib_dirs=[libdir])
    assert r.resolve("libm.so.6") == libdir / "libm.so.6"
    assert "libm.so.6" in r.resolvable_sonames()


def test_unknown_version_cache_falls_back_to_dirs(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "ld.so.cache"
    bad.write_bytes(b"glibc-ld.so.cache1.0" + b"\x00" * 8)  # unsupported version
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "libz.so.1").write_bytes(b"")
    r = HostLibResolver(62, cache_path=bad, lib_dirs=[libdir])
    assert r.resolve("libz.so.1") == libdir / "libz.so.1"


def test_non_library_files_in_lib_dir_not_resolvable(tmp_path: pathlib.Path) -> None:
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "readme.txt").write_bytes(b"")
    (libdir / "libc.so.6").write_bytes(b"")
    r = HostLibResolver(62, cache_path=tmp_path / "absent", lib_dirs=[libdir])
    assert r.resolve("readme.txt") is None
    assert "readme.txt" not in r.resolvable_sonames()
    assert r.resolve("libc.so.6") == libdir / "libc.so.6"


def test_never_uses_process_env_or_own_bundle(
    tmp_path: pathlib.Path,
    monkeypatch: MonkeyPatch,
) -> None:
    # Nuitka policy: even if LD_LIBRARY_PATH points at a progcache-shaped
    # directory containing a library, the resolver must not see it.
    progcache = tmp_path / "ruyi" / "progcache" / "0.1.0" / "linux-x86_64"
    progcache.mkdir(parents=True)
    (progcache / "libc.so.6").write_bytes(b"")
    monkeypatch.setenv("LD_LIBRARY_PATH", str(progcache))
    r = HostLibResolver(62, cache_path=tmp_path / "absent", lib_dirs=[])
    assert r.resolve("libc.so.6") is None
    assert "libc.so.6" not in r.resolvable_sonames()
