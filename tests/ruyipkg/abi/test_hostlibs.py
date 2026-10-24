import pathlib
import struct

from pytest import MonkeyPatch

from ruyi.ruyipkg.abi.hostlibs import HostLibResolver

_CACHE_MAGIC = b"glibc-ld.so.cache"
_CACHE_VERSION = b"1.1"
_FLAG_ELF_LIBC6 = 0x0003
_FLAG_X8664_LIB64 = 0x0200


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
    cache = build_cache(
        [
            (
                "libc.so.6",
                "/lib/x86_64-linux-gnu/libc.so.6",
                _FLAG_ELF_LIBC6 | _FLAG_X8664_LIB64,
            ),
            ("libc.so.6", "/lib32/libc.so.6", _FLAG_ELF_LIBC6),  # 32-bit: filtered out
        ]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert str(r.resolve("libc.so.6")).endswith("x86_64-linux-gnu/libc.so.6")


def test_multilib_cache_entry_filtered_by_flags(tmp_path: pathlib.Path) -> None:
    # A foreign-class (32-bit) entry alone must never be offered as provider.
    cache = build_cache(
        [
            ("libc.so.6", "/lib/i386-linux-gnu/libc.so.6", _FLAG_ELF_LIBC6),
        ]
    )
    (tmp_path / "ld.so.cache").write_bytes(cache)
    r = HostLibResolver(62, cache_path=tmp_path / "ld.so.cache", lib_dirs=())
    assert r.resolve("libc.so.6") is None
    assert "libc.so.6" not in r.resolvable_sonames()


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
