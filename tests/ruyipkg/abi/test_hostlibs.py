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


def build_cache(
    entries: list[tuple[str, str, int] | tuple[str, str, int, int]],
) -> bytes:
    """entries: (soname, path, flags[, hwcap]); glibc new-format layout."""
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
        struct.pack(
            "<iIIIQ",
            e[2],
            intern(e[0]),
            intern(e[1]),
            0,
            e[3] if len(e) > 3 else 0,
        )
        for e in entries
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
    (libdir / "libm.so.6").write_bytes(_elf_header(62))
    r = HostLibResolver(62, cache_path=bad, lib_dirs=[libdir])
    assert r.resolve("libm.so.6") == libdir / "libm.so.6"
    assert "libm.so.6" in r.resolvable_sonames()


def test_unknown_version_cache_falls_back_to_dirs(tmp_path: pathlib.Path) -> None:
    bad = tmp_path / "ld.so.cache"
    bad.write_bytes(b"glibc-ld.so.cache1.0" + b"\x00" * 8)  # unsupported version
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "libz.so.1").write_bytes(_elf_header(62))
    r = HostLibResolver(62, cache_path=bad, lib_dirs=[libdir])
    assert r.resolve("libz.so.1") == libdir / "libz.so.1"


def test_non_library_files_in_lib_dir_not_resolvable(tmp_path: pathlib.Path) -> None:
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "readme.txt").write_bytes(b"")
    (libdir / "libc.so.6").write_bytes(_elf_header(62))
    r = HostLibResolver(62, cache_path=tmp_path / "absent", lib_dirs=[libdir])
    assert r.resolve("readme.txt") is None
    assert "readme.txt" not in r.resolvable_sonames()
    assert r.resolve("libc.so.6") == libdir / "libc.so.6"


def test_resolve_soname_without_so_in_the_name(tmp_path: pathlib.Path) -> None:
    # Sonames are not required to contain ".so"; only the requested name is
    # looked up now, so nothing needs a filename filter any more.
    libdir = tmp_path / "lib"
    libdir.mkdir()
    lib = libdir / "libweird"
    lib.write_bytes(_elf_header(62))
    r = HostLibResolver(62, cache_path=tmp_path / "absent", lib_dirs=[libdir])
    assert r.resolve("libweird") == lib


def test_soname_with_path_separator_is_not_joined(tmp_path: pathlib.Path) -> None:
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (tmp_path / "evil.so").write_bytes(_elf_header(62))
    r = HostLibResolver(62, cache_path=tmp_path / "absent", lib_dirs=[libdir])
    assert r.resolve("../evil.so") is None


def test_only_requested_sonames_are_looked_up_in_dirs(
    tmp_path: pathlib.Path,
) -> None:
    libdir = tmp_path / "lib"
    libdir.mkdir()
    (libdir / "libother.so").write_bytes(_elf_header(62))
    r = HostLibResolver(62, cache_path=tmp_path / "absent", lib_dirs=[libdir])
    assert "libother.so" not in r.resolvable_sonames()
    assert r.resolve("libother.so") == libdir / "libother.so"


def test_resolve_skips_wrong_class_cache_candidate(tmp_path: pathlib.Path) -> None:
    # A stale or bogus cache entry must not mask a usable directory fallback.
    wrong = tmp_path / "lib32" / "libc.so.6"
    wrong.parent.mkdir()
    wrong.write_bytes(_elf_header(3, elf_class=1))
    libdir = tmp_path / "lib64"
    libdir.mkdir()
    right = libdir / "libc.so.6"
    right.write_bytes(_elf_header(62))
    cache = build_cache(
        [("libc.so.6", str(wrong), _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64)]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=[libdir])
    assert r.resolve("libc.so.6") == right


def test_resolve_skips_stale_cache_candidate(tmp_path: pathlib.Path) -> None:
    libdir = tmp_path / "lib64"
    libdir.mkdir()
    right = libdir / "libc.so.6"
    right.write_bytes(_elf_header(62))
    cache = build_cache(
        [
            (
                "libc.so.6",
                str(tmp_path / "gone" / "libc.so.6"),
                _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64,
            )
        ]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=[libdir])
    assert r.resolve("libc.so.6") == right


def test_resolve_rejects_wrong_class_only_candidate(tmp_path: pathlib.Path) -> None:
    lib = tmp_path / "libc.so.6"
    lib.write_bytes(_elf_header(3, elf_class=1))
    cache = build_cache([("libc.so.6", str(lib), _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64)])
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert r.resolve("libc.so.6") is None
    assert "libc.so.6" not in r.resolvable_sonames()


def test_hwcap_cache_entry_is_skipped(tmp_path: pathlib.Path) -> None:
    # We do not decode the glibc-hwcaps extension, so an entry carrying a
    # non-zero hwcap must not shadow a plain entry the loader would use.
    hwcap_lib = tmp_path / "v3" / "libc.so.6"
    hwcap_lib.parent.mkdir()
    hwcap_lib.write_bytes(_elf_header(62))
    plain = tmp_path / "plain" / "libc.so.6"
    plain.parent.mkdir()
    plain.write_bytes(_elf_header(62))
    cache = build_cache(
        [
            ("libc.so.6", str(hwcap_lib), _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64, 0x10),
            ("libc.so.6", str(plain), _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64),
        ]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert r.resolve("libc.so.6") == plain


def test_hwcap_only_cache_entry_is_not_used(tmp_path: pathlib.Path) -> None:
    lib = tmp_path / "v3" / "libc.so.6"
    lib.parent.mkdir()
    lib.write_bytes(_elf_header(62))
    cache = build_cache(
        [("libc.so.6", str(lib), _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64, 0x10)]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert r.resolve("libc.so.6") is None


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
