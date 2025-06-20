import glob
import os
from os import PathLike
import pathlib
import re
import shutil
from typing import Any, Final, Iterator, TypedDict

from ...config import GlobalConfig
from ...log import RuyiLogger, humanize_list
from ...ruyipkg.atom import Atom
from ...ruyipkg.pkg_manifest import EmulatorProgDecl
from ...ruyipkg.profile import ProfileProxy
from ...utils.global_mode import ProvidesGlobalMode
from . import ConfiguredTargetTuple
from .emulator_cfg import ResolvedEmulatorProg
from .templating import render_template_str


def do_make_venv(
    config: GlobalConfig,
    host: str,
    profile_name: str,
    dest: pathlib.Path,
    with_sysroot: bool,
    override_name: str | None = None,
    tc_atoms_str: list[str] | None = None,
    emu_atom_str: str | None = None,
    sysroot_atom_str: str | None = None,
    extra_cmd_atoms_str: list[str] | None = None,
) -> int:
    logger = config.logger

    # TODO: support omitting this if user only has one toolchain installed
    # this should come after implementation of local state cache
    if tc_atoms_str is None:
        logger.F(
            "You have to specify at least one toolchain atom for now, e.g. [yellow]`-t gnu-plct`[/]"
        )
        return 1

    mr = config.repo

    profile = mr.get_profile(profile_name)
    if profile is None:
        logger.F(f"profile '{profile_name}' not found")
        return 1

    target_arch = ""
    seen_target_tuples: set[str] = set()
    targets: list[ConfiguredTargetTuple] = []
    warn_differing_target_arch = False

    for tc_atom_str in tc_atoms_str:
        tc_atom = Atom.parse(tc_atom_str)
        tc_pm = tc_atom.match_in_repo(mr, config.include_prereleases)
        if tc_pm is None:
            logger.F(f"cannot match a toolchain package with [yellow]{tc_atom_str}[/]")
            return 1

        if tc_pm.toolchain_metadata is None:
            logger.F(f"the package [yellow]{tc_atom_str}[/] is not a toolchain")
            return 1

        if not tc_pm.toolchain_metadata.satisfies_quirk_set(profile.need_quirks):
            logger.F(
                f"the package [yellow]{tc_atom_str}[/] does not support all necessary features for the profile [yellow]{profile_name}[/]"
            )
            logger.I(
                f"quirks needed by profile:   {humanize_list(profile.need_quirks, item_color='cyan')}"
            )
            logger.I(
                f"quirks provided by package: {humanize_list(tc_pm.toolchain_metadata.quirks, item_color='yellow')}"
            )
            return 1

        target_tuple = tc_pm.toolchain_metadata.target
        if target_tuple in seen_target_tuples:
            logger.F(
                f"the target tuple [yellow]{target_tuple}[/] is already covered by one of the requested toolchains"
            )
            logger.I(
                "for now, only toolchains with differing target tuples can co-exist in one virtual environment"
            )
            return 1

        toolchain_root = config.lookup_binary_install_dir(
            host,
            tc_pm.name_for_installation,
        )
        if toolchain_root is None:
            logger.F("cannot find the installed directory for the toolchain")
            return 1

        tc_sysroot_dir: PathLike[Any] | None = None
        gcc_install_dir: PathLike[Any] | None = None
        if with_sysroot:
            if tc_sysroot_relpath := tc_pm.toolchain_metadata.included_sysroot:
                tc_sysroot_dir = pathlib.Path(toolchain_root) / tc_sysroot_relpath
            else:
                if sysroot_atom_str is None:
                    logger.F(
                        "sysroot is requested but the toolchain package does not include one, and [yellow]--sysroot-from[/] is not given"
                    )
                    return 1

                # try extracting from the sysroot package
                # for now only GCC toolchain packages can provide sysroots, so this is
                # okay
                gcc_pkg_atom = Atom.parse(sysroot_atom_str)
                gcc_pkg_pm = gcc_pkg_atom.match_in_repo(mr, config.include_prereleases)
                if gcc_pkg_pm is None:
                    logger.F(
                        f"cannot match a toolchain package with [yellow]{sysroot_atom_str}[/]"
                    )
                    return 1

                if gcc_pkg_pm.toolchain_metadata is None:
                    logger.F(
                        f"the package [yellow]{sysroot_atom_str}[/] is not a toolchain"
                    )
                    return 1

                gcc_pkg_root = config.lookup_binary_install_dir(
                    host,
                    gcc_pkg_pm.name_for_installation,
                )
                if gcc_pkg_root is None:
                    logger.F(
                        "cannot find the installed directory for the sysroot package"
                    )
                    return 1

                tc_sysroot_relpath = gcc_pkg_pm.toolchain_metadata.included_sysroot
                if tc_sysroot_relpath is None:
                    logger.F(
                        f"sysroot is requested but the package [yellow]{sysroot_atom_str}[/] does not contain one"
                    )
                    return 1

                tc_sysroot_dir = pathlib.Path(gcc_pkg_root) / tc_sysroot_relpath

                # also figure the GCC include/libs path out for Clang to be able to
                # locate them
                gcc_install_dir = find_gcc_install_dir(
                    gcc_pkg_root,
                    # we should use the GCC-providing package's target tuple as that's
                    # not guaranteed to be the same as llvm's
                    gcc_pkg_pm.toolchain_metadata.target,
                )

                # for now, require this directory to be present (or clang would barely work)
                if gcc_install_dir is None:
                    logger.F(
                        "cannot find a GCC include & lib directory in the sysroot package"
                    )
                    return 1

        # derive flags for (the quirks of) this toolchain
        tc_flags = profile.get_common_flags(tc_pm.toolchain_metadata.quirks)

        # record the target tuple info to configure in the venv
        configured_target: ConfiguredTargetTuple = {
            "target": target_tuple,
            "toolchain_root": toolchain_root,
            "toolchain_sysroot": tc_sysroot_dir,
            "toolchain_flags": tc_flags,
            # assume clang is preferred if package contains clang
            # this is mostly true given most packages don't contain both
            "cc_flavor": "clang" if tc_pm.toolchain_metadata.has_clang else "gcc",
            # same for binutils provider flavor
            "binutils_flavor": (
                "llvm" if tc_pm.toolchain_metadata.has_llvm else "binutils"
            ),
            "gcc_install_dir": gcc_install_dir,
        }
        logger.D(f"configuration for {target_tuple}: {configured_target}")
        targets.append(configured_target)
        seen_target_tuples.add(target_tuple)

        # record the target architecture for use in emulator package matching
        if not target_arch:
            target_arch = tc_pm.toolchain_metadata.target_arch
        elif target_arch != tc_pm.toolchain_metadata.target_arch:
            # first one wins
            warn_differing_target_arch = True

    if warn_differing_target_arch:
        logger.W("multiple toolchains specified with differing target architecture")
        logger.I(
            f"using the target architecture of the first toolchain: [yellow]{target_arch}[/]"
        )

    # Now handle the emulator.
    emu_progs = None
    emu_root: PathLike[Any] | None = None
    if emu_atom_str:
        emu_atom = Atom.parse(emu_atom_str)
        emu_pm = emu_atom.match_in_repo(mr, config.include_prereleases)
        if emu_pm is None:
            logger.F(f"cannot match an emulator package with [yellow]{emu_atom_str}[/]")
            return 1

        if emu_pm.emulator_metadata is None:
            logger.F(f"the package [yellow]{emu_atom_str}[/] is not an emulator")
            return 1

        emu_progs = list(emu_pm.emulator_metadata.list_for_arch(target_arch))
        if not emu_progs:
            logger.F(
                f"the emulator package [yellow]{emu_atom_str}[/] does not support the target architecture [yellow]{target_arch}[/]"
            )
            return 1

        for prog in emu_progs:
            if not profile.check_emulator_flavor(
                prog.flavor,
                emu_pm.emulator_metadata.quirks,
            ):
                logger.F(
                    f"the package [yellow]{emu_atom_str}[/] does not support all necessary features for the profile [yellow]{profile_name}[/]"
                )
                logger.I(
                    f"quirks needed by profile:   {humanize_list(profile.get_needed_emulator_pkg_flavors(prog.flavor), item_color='cyan')}"
                )
                logger.I(
                    f"quirks provided by package: {humanize_list(emu_pm.emulator_metadata.quirks or [], item_color='yellow')}"
                )
                return 1

        emu_root = config.lookup_binary_install_dir(
            host,
            emu_pm.name_for_installation,
        )
        if emu_root is None:
            logger.F("cannot find the installed directory for the emulator")
            return 1

    # Now resolve extra commands to provide in the venv.
    extra_cmds: dict[str, str] = {}
    if extra_cmd_atoms_str:
        for extra_cmd_atom_str in extra_cmd_atoms_str:
            extra_cmd_atom = Atom.parse(extra_cmd_atom_str)
            extra_cmd_pm = extra_cmd_atom.match_in_repo(
                mr,
                config.include_prereleases,
            )
            if extra_cmd_pm is None:
                logger.F(
                    f"cannot match an extra command package with [yellow]{extra_cmd_atom_str}[/]"
                )
                return 1

            extra_cmd_bm = extra_cmd_pm.binary_metadata
            if not extra_cmd_bm:
                logger.F(
                    f"the package [yellow]{extra_cmd_atom_str}[/] is not a binary-providing package"
                )
                return 1

            extra_cmds_decl = extra_cmd_bm.get_commands_for_host(host)
            if not extra_cmds_decl:
                logger.W(
                    f"the package [yellow]{extra_cmd_atom_str}[/] does not provide any command for host [yellow]{host}[/], ignoring"
                )
                continue

            cmd_root = config.lookup_binary_install_dir(
                host,
                extra_cmd_pm.name_for_installation,
            )
            if cmd_root is None:
                logger.F(
                    f"cannot find the installed directory for the package [yellow]{extra_cmd_pm.name_for_installation}[/]"
                )
                return 1
            cmd_root = pathlib.Path(cmd_root)

            for cmd, cmd_rel_path in extra_cmds_decl.items():
                # resolve the command path
                cmd_path = (cmd_root / cmd_rel_path).resolve()
                if not cmd_path.is_relative_to(cmd_root):
                    # we don't allow commands to resolve outside of the
                    # providing package's install root
                    logger.F(
                        "internal error: resolved command path is outside of the providing package"
                    )
                    return 1

                # add the command to the list
                extra_cmds[cmd] = str(cmd_path)

    if override_name is not None:
        logger.I(
            f"Creating a Ruyi virtual environment [cyan]'{override_name}'[/] at [green]{dest}[/]..."
        )
    else:
        logger.I(f"Creating a Ruyi virtual environment at [green]{dest}[/]...")

    maker = VenvMaker(
        config,
        profile,
        targets,
        dest.resolve(),
        emu_progs,
        emu_root,
        extra_cmds,
        override_name,
    )
    maker.provision()

    logger.I(
        render_template_str(
            "prompt.venv-created.txt",
            {
                "sysroot": maker.sysroot_destdir(None),
            },
        )
    )

    return 0


def find_gcc_install_dir(
    install_root: PathLike[Any],
    target_tuple: str,
) -> PathLike[Any] | None:
    # check $PREFIX/lib/gcc/$TARGET/*
    search_root = pathlib.Path(install_root) / "lib" / "gcc" / target_tuple
    try:
        for p in search_root.iterdir():
            # only want the first one (should be the only one)
            return p
    except FileNotFoundError:
        pass

    # nothing?
    return None


class VenvMaker:
    """Performs the actual creation of a Ruyi virtual environment."""

    def __init__(
        self,
        gc: GlobalConfig,
        profile: ProfileProxy,
        targets: list[ConfiguredTargetTuple],
        dest: PathLike[Any],
        emulator_progs: list[EmulatorProgDecl] | None,
        emulator_root: PathLike[Any] | None,
        extra_cmds: dict[str, str] | None,
        override_name: str | None = None,
    ) -> None:
        self.gc = gc
        self.profile = profile
        self.targets = targets
        self.venv_root = pathlib.Path(dest)
        self.emulator_progs = emulator_progs
        self.emulator_root = emulator_root
        self.extra_cmds = extra_cmds or {}
        self.override_name = override_name

        self.bindir = self.venv_root / "bin"

    @property
    def logger(self) -> RuyiLogger:
        return self.gc.logger

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

        if self.extra_cmds:
            symlink_binaries(
                self.gc,
                self.logger,
                bindir,
                src_cmds_names=list(self.extra_cmds.keys()),
            )

        template_data = {
            "RUYI_VENV": str(venv_root),
            "RUYI_VENV_NAME": self.override_name,
        }

        self.render_and_write(
            bindir / "ruyi-activate",
            "ruyi-activate.bash",
            template_data,
        )

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
                os.symlink(self.gc.self_exe, bindir / "ruyi-qemu")

        # provide initial cached configuration to venv
        self.render_and_write(
            venv_root / "ruyi-cache.v2.toml",
            "ruyi-cache.toml",
            self.make_venv_cache_data(
                qemu_bin,
                self.extra_cmds,
                profile_emu_env,
            ),
        )

    def make_venv_cache_data(
        self,
        qemu_bin: PathLike[Any] | None,
        extra_cmds: dict[str, str],
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

        # add extra cmds that are not associated with any target
        for cmd, dest in extra_cmds.items():
            if cmd in cmd_metadata_map:
                self.logger.W(
                    f"extra command {cmd} is already provided by another package, overriding it"
                )
            cmd_metadata_map[cmd] = {
                "dest": dest,
                "target_tuple": "",
            }

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
        symlink_binaries(self.gc, self.logger, bindir, src_bindir=toolchain_bindir)

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
    gm: ProvidesGlobalMode,
    logger: RuyiLogger,
    dest_bindir: PathLike[Any],
    *,
    src_bindir: PathLike[Any] | None = None,
    src_cmds_names: list[str] | None = None,
) -> None:
    dest_binpath = pathlib.Path(dest_bindir)
    self_exe_path = gm.self_exe

    if src_bindir is not None:
        src_binpath = pathlib.Path(src_bindir)
        for src_cmd_path in iter_binaries_to_symlink(logger, src_binpath):
            filename = src_cmd_path.name

            # symlink self to dest with the name of this command
            dest_path = dest_binpath / filename
            logger.D(f"making ruyi symlink to {self_exe_path} at {dest_path}")
            os.symlink(self_exe_path, dest_path)
        return

    if src_cmds_names is not None:
        for cmd in src_cmds_names:
            # symlink self to dest with the name of this command
            dest_path = dest_binpath / cmd
            logger.D(f"making ruyi symlink to {self_exe_path} at {dest_path}")
            os.symlink(self_exe_path, dest_path)
        return

    raise ValueError(
        "internal error: either src_bindir or src_cmds_names must be provided"
    )


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
