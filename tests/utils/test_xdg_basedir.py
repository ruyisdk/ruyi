import os
import pathlib
from unittest import mock

import sys

import pytest

from ruyi.utils.xdg_basedir import XDGBaseDir, XDGPathEntry


def test_xdg_macos_defaults() -> None:
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


def test_xdg_macos_system_dirs_are_empty() -> None:
    with (
        mock.patch.object(sys, "platform", "darwin"),
        mock.patch.dict(os.environ, {}, clear=True),
    ):
        dirs = XDGBaseDir("ruyi")
        assert list(dirs.config_dirs) == []
        assert list(dirs.data_dirs) == []


def test_xdg_macos_env_override_still_works() -> None:
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


def test_xdg_macos_config_dirs_env_override() -> None:
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


def test_xdg_linux_defaults_unchanged() -> None:
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


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize(
    "attribute,env,linux_suffix,macos_suffix",
    [
        ("cache_home", "XDG_CACHE_HOME", ".cache", "Library/Caches"),
        ("config_home", "XDG_CONFIG_HOME", ".config", "Library/Preferences"),
        ("data_home", "XDG_DATA_HOME", ".local/share", "Library/Application Support"),
        ("state_home", "XDG_STATE_HOME", ".local/state", "Library/Application Support"),
    ],
)
def test_xdg_home_ignores_relative_override(
    platform: str,
    attribute: str,
    env: str,
    linux_suffix: str,
    macos_suffix: str,
) -> None:
    home = pathlib.Path("/test/home")
    with (
        mock.patch.object(pathlib.Path, "home", return_value=home),
        mock.patch.object(sys, "platform", platform),
        mock.patch.dict(os.environ, {env: "relative-location"}, clear=True),
    ):
        expected = home / (macos_suffix if platform == "darwin" else linux_suffix)
        assert getattr(XDGBaseDir("ruyi"), attribute) == expected


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize(
    "attribute,env",
    [
        ("cache_home", "XDG_CACHE_HOME"),
        ("config_home", "XDG_CONFIG_HOME"),
        ("data_home", "XDG_DATA_HOME"),
        ("state_home", "XDG_STATE_HOME"),
    ],
)
def test_xdg_home_preserves_absolute_override(
    platform: str, attribute: str, env: str
) -> None:
    with (
        mock.patch.object(sys, "platform", platform),
        mock.patch.dict(os.environ, {env: "/custom/location"}, clear=True),
    ):
        assert getattr(XDGBaseDir("ruyi"), attribute) == pathlib.Path("/custom/location")


@pytest.mark.parametrize("platform", ["linux", "darwin"])
@pytest.mark.parametrize(
    "attribute,env", [("config_dirs", "XDG_CONFIG_DIRS"), ("data_dirs", "XDG_DATA_DIRS")]
)
def test_xdg_dirs_ignore_relative_entries(platform: str, attribute: str, env: str) -> None:
    with (
        mock.patch.object(sys, "platform", platform),
        mock.patch.dict(
            os.environ,
            {env: "relative:/first::../relative:/second/"},
            clear=True,
        ),
    ):
        assert list(getattr(XDGBaseDir("ruyi"), attribute)) == [
            XDGPathEntry(pathlib.Path("/first"), True),
            XDGPathEntry(pathlib.Path("/second"), True),
        ]
