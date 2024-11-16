import os
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self

from ...ruyipkg.pkg_manifest import EmulatorProgDecl
from ...ruyipkg.profile import ProfileProxy


class ResolvedEmulatorProg:
    def __init__(
        self,
        display_name: str,
        binfmt_misc_str: str | None,
        env: dict[str, str] | None,
    ) -> None:
        self.display_name = display_name
        self.binfmt_misc_str = binfmt_misc_str
        self.env = env

    @classmethod
    def new(
        cls,
        prog: EmulatorProgDecl,
        prog_install_root: os.PathLike[Any],
        profile: ProfileProxy,
        sysroot: os.PathLike[Any] | None,
    ) -> "Self":
        return cls(
            get_display_name_for_emulator(prog, prog_install_root),
            prog.get_binfmt_misc_str(prog_install_root),
            profile.get_env_config_for_emu_flavor(prog.flavor, sysroot),
        )


def get_display_name_for_emulator(
    prog: EmulatorProgDecl,
    prog_install_root: os.PathLike[Any],
) -> str:
    return f"{os.path.basename(prog.relative_path)} from {prog_install_root}"
