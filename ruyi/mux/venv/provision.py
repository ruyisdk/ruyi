import base64
import glob
import os
from os import PathLike
import pathlib
import re
import shlex
import shutil
from typing import Any, Final, Callable, Iterator, Tuple, TypedDict
import zlib

from jinja2 import BaseLoader, Environment, TemplateNotFound

from ... import self_exe
from ...config import GlobalConfig
from ...log import RuyiLogger
from ...ruyipkg.pkg_manifest import EmulatorProgDecl
from ...ruyipkg.profile import ProfileProxy
from . import ConfiguredTargetTuple
from .data import TEMPLATES
from .emulator_cfg import ResolvedEmulatorProg


def unpack_payload(x: bytes) -> str:
    return zlib.decompress(base64.b64decode(x)).decode("utf-8")


class EmbeddedLoader(BaseLoader):
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> Tuple[str, str | None, Callable[[], bool] | None]:
        payload = self._payloads.get(template)
        if payload is None:
            raise TemplateNotFound(template)
        return unpack_payload(payload), None, None


JINJA_ENV: Final = Environment(
    loader=EmbeddedLoader(TEMPLATES),
    autoescape=False,  # we're not producing HTML
    auto_reload=False,  # we're serving statically embedded assets
    keep_trailing_newline=True,  # to make shells happy
)
JINJA_ENV.filters["sh"] = shlex.quote


def render_template_str(template_name: str, data: dict[str, Any]) -> str:
    tmpl = JINJA_ENV.get_template(template_name)
    return tmpl.render(data)



class VenvMaker:
    def __init__(
        self,
        gc: GlobalConfig,
        profile: ProfileProxy,
        targets: list[ConfiguredTargetTuple],
        dest: PathLike[Any],
        emulator_progs: list[EmulatorProgDecl] | None,
        emulator_root: PathLike[Any] | None,
        override_name: str | None = None,
    ) -> None:
        self.logger = gc.logger
        self.profile = profile
        self.targets = targets
        self.venv_root = pathlib.Path(dest)
        self.emulator_progs = emulator_progs
        self.emulator_root = emulator_root
        self.override_name = override_name

        self.bindir = self.venv_root / "bin"

    def render_and_write(
        self,
        dest: PathLike[Any],
        template_name: str,
        data: dict[str, Any],
    ) -> None:
        self.logger.D(f"rendering template '{template_name}' with data {data}")
        content = render_template_str(template_name, data).encode("utf-8")
        self.logger.D(f"writing {dest}")
        with open(dest, "wb") as fp:
            fp.write(content)

    def sysroot_srcdir(self, target_tuple: str | None) -> pathlib.Path | None:
        if target_tuple is None:
            # check the primary target
            if s := self.targets[0]["toolchain_sysroot"]:
                return pathlib.Path(s)
            return None

        # check if we have this target
        for t in self.targets:
            if t["target"] != target_tuple:
                continue
            if s := t["toolchain_sysroot"]:
                return pathlib.Path(s)

        return None

    def has_sysroot_for(self, target_tuple: str | None) -> bool:
        return self.sysroot_srcdir(target_tuple) is not None

    def sysroot_destdir(self, target_tuple: str | None) -> pathlib.Path | None:
        if not self.has_sysroot_for(target_tuple):
            return None

        dirname = f"sysroot.{target_tuple}" if target_tuple is not None else "sysroot"
        return self.venv_root / dirname

    def provision(self) -> None:
        venv_root = self.venv_root
        bindir = self.bindir

        venv_root.mkdir()
        bindir.mkdir()

        env_data = {
            "profile": self.profile.id,
            "sysroot": self.sysroot_destdir(None),
        }
        self.render_and_write(
            venv_root / "ruyi-venv.toml",
            "ruyi-venv.toml",
            env_data,
        )

        for i, tgt in enumerate(self.targets):
            is_primary = i == 0
            self.provision_target(tgt, is_primary)

        template_data = {
            "RUYI_VENV": str(venv_root),
            "RUYI_VENV_NAME": self.override_name,
        }

        self.render_and_write(bindir / "ruyi-activate", "ruyi-activate.bash", template_data)

        qemu_bin: PathLike[Any] | None = None
        profile_emu_env: dict[str, str] | None = None
        if self.emulator_root is not None and self.emulator_progs:
            resolved_emu_progs = [
                ResolvedEmulatorProg.new(
                    p,
                    self.emulator_root,
                    self.profile,
                    self.sysroot_destdir(None),
                )
                for p in self.emulator_progs
            ]
            binfmt_data = {
                "resolved_progs": resolved_emu_progs,
            }
            self.render_and_write(
                venv_root / "binfmt.conf",
                "binfmt.conf",
                binfmt_data,
            )

            for i, p in enumerate(self.emulator_progs):
                if not p.is_qemu:
                    continue

                qemu_bin = pathlib.Path(self.emulator_root) / p.relative_path
                profile_emu_env = resolved_emu_progs[i].env

                self.logger.D("symlinking the ruyi-qemu wrapper")
                os.symlink(self_exe(), bindir / "ruyi-qemu")

        # provide initial cached configuration to venv
        self.render_and_write(
            venv_root / "ruyi-cache.v2.toml",
            "ruyi-cache.toml",
            self.make_venv_cache_data(
                qemu_bin,
                profile_emu_env,
            ),
        )

    def make_venv_cache_data(
        self,
        qemu_bin: PathLike[Any] | None,
        profile_emu_env: dict[str, str] | None,
    ) -> dict[str, object]:
        targets_cache_data: dict[str, object] = {
            tgt["target"]: {
                "toolchain_bindir": str(pathlib.Path(tgt["toolchain_root"]) / "bin"),
                "toolchain_sysroot": self.sysroot_destdir(tgt["target"]),
                "toolchain_flags": tgt["toolchain_flags"],
                "gcc_install_dir": tgt["gcc_install_dir"],
            }
            for tgt in self.targets
        }

        cmd_metadata_map = make_cmd_metadata_map(self.logger, self.targets)

        return {
            "profile_emu_env": profile_emu_env,
            "qemu_bin": qemu_bin,
            "targets": targets_cache_data,
            "cmd_metadata_map": cmd_metadata_map,
        }

    def provision_target(
        self,
        tgt: ConfiguredTargetTuple,
        is_primary: bool,
    ) -> None:
        venv_root = self.venv_root
        bindir = self.bindir
        target_tuple = tgt["target"]

        # getting the destdir this way ensures it's suffixed with the target
        # tuple
        if sysroot_destdir := self.sysroot_destdir(target_tuple):
            sysroot_srcdir = tgt["toolchain_sysroot"]
            assert sysroot_srcdir is not None

            self.logger.D(f"copying sysroot for {target_tuple}")
            shutil.copytree(
                sysroot_srcdir,
                sysroot_destdir,
                symlinks=True,
                ignore_dangling_symlinks=True,
            )

            if is_primary:
                self.logger.D("symlinking primary sysroot into place")
                primary_sysroot_destdir = self.sysroot_destdir(None)
                assert primary_sysroot_destdir is not None
                os.symlink(sysroot_destdir.name, primary_sysroot_destdir)

        self.logger.D(f"symlinking {target_tuple} binaries into venv")
        toolchain_bindir = pathlib.Path(tgt["toolchain_root"]) / "bin"
        symlink_binaries(self.logger, toolchain_bindir, bindir)

        make_llvm_tool_aliases(
            self.logger,
            bindir,
            target_tuple,
            tgt["binutils_flavor"] == "llvm",
            tgt["cc_flavor"] == "clang",
        )

        # CMake toolchain file & Meson cross file
        if tgt["cc_flavor"] == "clang":
            cc_path = bindir / "clang"
            cxx_path = bindir / "clang++"
        elif tgt["cc_flavor"] == "gcc":
            cc_path = bindir / f"{target_tuple}-gcc"
            cxx_path = bindir / f"{target_tuple}-g++"
        else:
            raise NotImplementedError

        if tgt["binutils_flavor"] == "binutils":
            meson_additional_binaries = {
                "ar": bindir / f"{target_tuple}-ar",
                "nm": bindir / f"{target_tuple}-nm",
                "objcopy": bindir / f"{target_tuple}-objcopy",
                "objdump": bindir / f"{target_tuple}-objdump",
                "ranlib": bindir / f"{target_tuple}-ranlib",
                "readelf": bindir / f"{target_tuple}-readelf",
                "strip": bindir / f"{target_tuple}-strip",
            }
        elif tgt["binutils_flavor"] == "llvm":
            meson_additional_binaries = {
                "ar": bindir / "llvm-ar",
                "nm": bindir / "llvm-nm",
                "objcopy": bindir / "llvm-objcopy",
                "objdump": bindir / "llvm-objdump",
                "ranlib": bindir / "llvm-ranlib",
                "readelf": bindir / "llvm-readelf",
                "strip": bindir / "llvm-strip",
            }
        else:
            raise NotImplementedError

        cmake_toolchain_file_path = venv_root / f"toolchain.{target_tuple}.cmake"
        toolchain_file_data = {
            "cc": cc_path,
            "cxx": cxx_path,
            "processor": self.profile.arch,
            "sysroot": self.sysroot_destdir(target_tuple),
            "venv_root": venv_root,
            "cmake_toolchain_file": str(cmake_toolchain_file_path),
            "meson_additional_binaries": meson_additional_binaries,
        }
        self.render_and_write(
            cmake_toolchain_file_path,
            "toolchain.cmake",
            toolchain_file_data,
        )

        meson_cross_file_path = venv_root / f"meson-cross.{target_tuple}.ini"
        self.render_and_write(
            meson_cross_file_path,
            "meson-cross.ini",
            toolchain_file_data,
        )

        if is_primary:
            self.logger.D(
                f"making cmake & meson file symlinks to primary target {target_tuple}"
            )
            primary_cmake_toolchain_file_path = venv_root / "toolchain.cmake"
            primary_meson_cross_file_path = venv_root / "meson-cross.ini"
            os.symlink(
                cmake_toolchain_file_path.name,
                primary_cmake_toolchain_file_path,
            )
            os.symlink(meson_cross_file_path.name, primary_meson_cross_file_path)


def iter_binaries_to_symlink(
    logger: RuyiLogger,
    bindir: pathlib.Path,
) -> Iterator[pathlib.Path]:
    for filename in glob.iglob("*", root_dir=bindir):
        src_cmd_path = bindir / filename
        if not is_executable(src_cmd_path):
            logger.D(f"skipping non-executable {filename} in src bindir")
            continue

        if should_ignore_symlinking(filename):
            logger.D(f"skipping command {filename} explicitly")
            continue

        yield bindir / filename


class CmdMetadataEntry(TypedDict):
    dest: str
    target_tuple: str


def make_cmd_metadata_map(
    logger: RuyiLogger,
    targets: list[ConfiguredTargetTuple],
) -> dict[str, CmdMetadataEntry]:
    result: dict[str, CmdMetadataEntry] = {}
    for tgt in targets:
        # TODO: dedup this and provision_target
        toolchain_bindir = pathlib.Path(tgt["toolchain_root"]) / "bin"
        for cmd in iter_binaries_to_symlink(logger, toolchain_bindir):
            result[cmd.name] = {
                "dest": str(cmd),
                "target_tuple": tgt["target"],
            }
    return result


def symlink_binaries(
    logger: RuyiLogger,
    src_bindir: PathLike[Any],
    dest_bindir: PathLike[Any],
) -> None:
    src_binpath = pathlib.Path(src_bindir)
    dest_binpath = pathlib.Path(dest_bindir)
    self_exe_path = self_exe()

    for src_cmd_path in iter_binaries_to_symlink(logger, src_binpath):
        filename = src_cmd_path.name

        # symlink self to dest with the name of this command
        dest_path = dest_binpath / filename
        logger.D(f"making ruyi symlink to {self_exe_path} at {dest_path}")
        os.symlink(self_exe_path, dest_path)


LLVM_BINUTILS_ALIASES: Final = {
    "addr2line": "llvm-addr2line",
    "ar": "llvm-ar",
    "as": "llvm-as",
    "c++filt": "llvm-cxxfilt",
    "gcc-ar": "llvm-ar",
    "gcc-nm": "llvm-nm",
    "gcc-ranlib": "llvm-ranlib",
    # 'gcov': 'llvm-cov',  # I'm not sure if this is correct
    "ld": "ld.lld",
    "nm": "llvm-nm",
    "objcopy": "llvm-objcopy",
    "objdump": "llvm-objdump",
    "ranlib": "llvm-ranlib",
    "readelf": "llvm-readelf",
    "size": "llvm-size",
    "strings": "llvm-strings",
    "strip": "llvm-strip",
}

CLANG_GCC_ALIASES: Final = {
    "c++": "clang++",
    "cc": "clang",
    "cpp": "clang-cpp",
    "g++": "clang++",
    "gcc": "clang",
}


def make_llvm_tool_aliases(
    logger: RuyiLogger,
    dest_bindir: PathLike[Any],
    target_tuple: str,
    do_binutils: bool,
    do_clang: bool,
) -> None:
    if do_binutils:
        make_compat_symlinks(logger, dest_bindir, target_tuple, LLVM_BINUTILS_ALIASES)
    if do_clang:
        make_compat_symlinks(logger, dest_bindir, target_tuple, CLANG_GCC_ALIASES)


def make_compat_symlinks(
    logger: RuyiLogger,
    dest_bindir: PathLike[Any],
    target_tuple: str,
    aliases: dict[str, str],
) -> None:
    destdir = pathlib.Path(dest_bindir)
    for compat_basename, symlink_target in aliases.items():
        compat_name = f"{target_tuple}-{compat_basename}"
        logger.D(f"making compat symlink: {compat_name} -> {symlink_target}")
        os.symlink(symlink_target, destdir / compat_name)


def is_executable(p: PathLike[Any]) -> bool:
    return os.access(p, os.F_OK | os.X_OK)


def should_ignore_symlinking(c: str) -> bool:
    return is_command_specific_to_ct_ng(c) or is_command_versioned_cc(c)


def is_command_specific_to_ct_ng(c: str) -> bool:
    return c.endswith("populate") or c.endswith("ct-ng.config")


VERSIONED_CC_RE: Final = re.compile(
    r"(?:^|-)(?:g?cc|c\+\+|g\+\+|cpp|clang|clang\+\+)-[0-9.]+$"
)


def is_command_versioned_cc(c: str) -> bool:
    return VERSIONED_CC_RE.search(c) is not None
