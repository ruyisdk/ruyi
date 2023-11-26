import base64
import glob
import os
from os import PathLike
import pathlib
import re
import shlex
import shutil
from typing import Any, Callable, Tuple
import zlib

from jinja2 import BaseLoader, Environment, TemplateNotFound

from ... import log, self_exe
from ...ruyipkg.profile import ProfileDecl
from .data import TEMPLATES


def unpack_payload(x: bytes) -> str:
    return zlib.decompress(base64.b64decode(x)).decode("utf-8")


class EmbeddedLoader(BaseLoader):
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self._payloads = payloads

    def get_source(
        self, _: Environment, template: str
    ) -> Tuple[str, str | None, Callable[[], bool] | None]:
        payload = self._payloads.get(template)
        if payload is None:
            raise TemplateNotFound(template)
        return unpack_payload(payload), None, None


JINJA_ENV = Environment(
    loader=EmbeddedLoader(TEMPLATES),
    autoescape=False,  # we're not producing HTML
    auto_reload=False,  # we're serving statically embedded assets
    keep_trailing_newline=True,  # to make shells happy
)
JINJA_ENV.filters["sh"] = shlex.quote


def render_template_str(template_name: str, data: dict[str, Any]) -> str:
    tmpl = JINJA_ENV.get_template(template_name)
    return tmpl.render(data)


def render_and_write(dest: PathLike, template_name: str, data: dict[str, Any]) -> None:
    content = render_template_str(template_name, data).encode("utf-8")
    with open(dest, "wb") as fp:
        fp.write(content)


class VenvMaker:
    def __init__(
        self,
        profile: ProfileDecl,
        toolchain_install_root: str,
        dest: PathLike,
        sysroot_srcdir: PathLike | None,
        override_name: str | None = None,
    ) -> None:
        self.profile = profile
        self.toolchain_install_root = toolchain_install_root
        self.dest = dest
        self.sysroot_srcdir = sysroot_srcdir
        self.override_name = override_name

    def provision(self) -> None:
        venv_root = pathlib.Path(self.dest)
        venv_root.mkdir()

        sysroot_destdir = None
        if self.sysroot_srcdir is not None:
            sysroot_destdir = venv_root / "sysroot"
            shutil.copytree(
                self.sysroot_srcdir,
                sysroot_destdir,
                symlinks=True,
                ignore_dangling_symlinks=True,
            )

        env_data = {
            "profile": self.profile.name,
            "sysroot": sysroot_destdir,
        }
        render_and_write(venv_root / "ruyi-venv.toml", "ruyi-venv.toml", env_data)

        toolchain_bindir = pathlib.Path(self.toolchain_install_root) / "bin"
        initial_cache_data = {
            "toolchain_bindir": str(toolchain_bindir),
            "profile_common_flags": self.profile.get_common_flags(),
        }
        render_and_write(
            venv_root / "ruyi-cache.toml",
            "ruyi-cache.toml",
            initial_cache_data,
        )

        bindir = venv_root / "bin"
        bindir.mkdir()

        log.D("symlinking binaries into venv")
        symlink_binaries(toolchain_bindir, bindir)

        template_data = {
            "RUYI_VENV": str(self.dest),
            "RUYI_VENV_NAME": self.override_name,
        }

        render_and_write(bindir / "ruyi-activate", "ruyi-activate.bash", template_data)


def symlink_binaries(src_bindir: PathLike, dest_bindir: PathLike) -> None:
    src_binpath = pathlib.Path(src_bindir)
    dest_binpath = pathlib.Path(dest_bindir)
    self_exe_path = self_exe()

    for filename in glob.iglob("*", root_dir=src_bindir):
        if not is_executable(src_binpath / filename):
            log.D(f"skipping non-executable {filename} in src bindir")
            continue

        if should_ignore_symlinking(filename):
            log.D(f"skipping command {filename} explicitly")
            continue

        # symlink self to dest with the name of this command
        dest_path = dest_binpath / filename
        log.D(f"making ruyi symlink to {self_exe_path} at {dest_path}")
        os.symlink(self_exe_path, dest_path)


def is_executable(p: PathLike) -> bool:
    return os.access(p, os.F_OK | os.X_OK)


def should_ignore_symlinking(c: str) -> bool:
    return is_command_specific_to_ct_ng(c) or is_command_versioned_cc(c)


def is_command_specific_to_ct_ng(c: str) -> bool:
    return c.endswith("populate") or c.endswith("ct-ng.config")


VERSIONED_CC_RE = re.compile(
    r"(?:^|-)(?:g?cc|c\+\+|g\+\+|cpp|clang|clang\+\+)-[0-9.]+$"
)


def is_command_versioned_cc(c: str) -> bool:
    return VERSIONED_CC_RE.search(c) is not None
