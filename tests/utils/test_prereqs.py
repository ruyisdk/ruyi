import shutil
import sys
from unittest import mock

from ruyi.utils import prereqs


def test_ensure_cmds_only_checks_requested_commands() -> None:
    """ensure_cmds only cares about the commands passed to it, not all of _CMDS."""
    with mock.patch.object(
        shutil, "which", return_value=None
    ):
        with mock.patch.object(sys, "stdin", create=True) as mock_stdin:
            mock_stdin.isatty.return_value = False
            prereqs.init_cmd_presence_map()
            absent = sorted(
                c for c in ("tar", "gunzip") if not prereqs._CMD_PRESENCE_MAP.get(c)
            )
            assert absent == ["gunzip", "tar"]


def test_init_cmd_presence_map_platform_aware() -> None:
    """init_cmd_presence_map skips device-provisioning commands on macOS."""
    with mock.patch.object(
        shutil, "which", return_value=None
    ):
        with mock.patch.object(sys, "platform", "darwin"):
            prereqs.init_cmd_presence_map()
            assert "sudo" not in prereqs._CMD_PRESENCE_MAP
            assert "dd" not in prereqs._CMD_PRESENCE_MAP
            assert "fastboot" not in prereqs._CMD_PRESENCE_MAP
            assert "tar" in prereqs._CMD_PRESENCE_MAP
            assert "unzip" in prereqs._CMD_PRESENCE_MAP


def test_init_cmd_presence_map_linux_includes_all() -> None:
    """init_cmd_presence_map checks all commands on Linux."""
    with mock.patch.object(
        shutil, "which", return_value=None
    ):
        with mock.patch.object(sys, "platform", "linux"):
            prereqs.init_cmd_presence_map()
            assert "sudo" in prereqs._CMD_PRESENCE_MAP
            assert "dd" in prereqs._CMD_PRESENCE_MAP
            assert "fastboot" in prereqs._CMD_PRESENCE_MAP
            assert "tar" in prereqs._CMD_PRESENCE_MAP
