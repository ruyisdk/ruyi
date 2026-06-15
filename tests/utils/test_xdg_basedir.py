import os
import pathlib
from unittest import mock

import sys

from ruyi.utils.xdg_basedir import XDGBaseDir, XDGPathEntry


def test_xdg_macos_defaults():
    home = pathlib.Path("/Users/testuser")
    with (
        mock.patch.object(pathlib.Path, "home", return_value=home),
        mock.patch.object(sys, "platform", "darwin"),
        mock.patch.dict(os.environ, {}, clear=True),
    ):
        dirs = XDGBaseDir("ruyi")

        assert dirs.cache_home == home / "Library" / "Caches"
        assert dirs.config_home == home / "Library" / "Preferences"
        assert dirs.data_home == home / "Library" / "Application Support"
        assert dirs.state_home == home / "Library" / "Application Support"

        assert dirs.app_cache == home / "Library" / "Caches" / "ruyi"
        assert dirs.app_config == home / "Library" / "Preferences" / "ruyi"
        assert dirs.app_data == home / "Library" / "Application Support" / "ruyi"
        assert dirs.app_state == home / "Library" / "Application Support" / "ruyi"


def test_xdg_macos_system_dirs_are_empty():
    with (
        mock.patch.object(sys, "platform", "darwin"),
        mock.patch.dict(os.environ, {}, clear=True),
    ):
        dirs = XDGBaseDir("ruyi")
        assert list(dirs.config_dirs) == []
        assert list(dirs.data_dirs) == []


def test_xdg_macos_env_override_still_works():
    home = pathlib.Path("/Users/testuser")
    with (
        mock.patch.object(pathlib.Path, "home", return_value=home),
        mock.patch.object(sys, "platform", "darwin"),
        mock.patch.dict(
            os.environ,
            {
                "XDG_CACHE_HOME": "/custom/cache",
                "XDG_CONFIG_HOME": "/custom/config",
            },
        ),
    ):
        dirs = XDGBaseDir("ruyi")
        assert dirs.cache_home == pathlib.Path("/custom/cache")
        assert dirs.config_home == pathlib.Path("/custom/config")


def test_xdg_macos_config_dirs_env_override():
    with (
        mock.patch.object(sys, "platform", "darwin"),
        mock.patch.dict(
            os.environ,
            {"XDG_CONFIG_DIRS": "/Library/Preferences:/opt/config"},
        ),
    ):
        dirs = XDGBaseDir("ruyi")
        entries = list(dirs.config_dirs)
        assert len(entries) == 2
        assert {e.path for e in entries} == {
            pathlib.Path("/Library/Preferences"),
            pathlib.Path("/opt/config"),
        }


def test_xdg_linux_defaults_unchanged():
    """Ensure Linux defaults are not affected by macOS changes."""
    home = pathlib.Path("/home/testuser")
    with (
        mock.patch.object(pathlib.Path, "home", return_value=home),
        mock.patch.object(sys, "platform", "linux"),
        mock.patch.dict(os.environ, {}, clear=True),
    ):
        dirs = XDGBaseDir("ruyi")

        assert dirs.cache_home == home / ".cache"
        assert dirs.config_home == home / ".config"
        assert dirs.data_home == home / ".local" / "share"
        assert dirs.state_home == home / ".local" / "state"

        assert list(dirs.config_dirs) == [
            XDGPathEntry(pathlib.Path("/etc/xdg"), True),
        ]
