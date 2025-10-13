import pathlib
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import pytest

from ruyi.config.editor import ConfigEditor
from ruyi.config.errors import (
    InvalidConfigKeyError,
    InvalidConfigSectionError,
    InvalidConfigValueTypeError,
    MalformedConfigFileError,
    ProtectedGlobalConfigError,
)


@pytest.fixture
def temp_config_file(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "config.toml"


def test_enter_exit(temp_config_file: pathlib.Path) -> None:
    editor = ConfigEditor(temp_config_file)
    with editor as e:
        assert e is editor
        e.set_value("telemetry.mode", "off")
    # no stage() so no file writing
    assert not temp_config_file.exists()


def test_set_value(temp_config_file: pathlib.Path) -> None:
    with ConfigEditor(temp_config_file) as e:
        with pytest.raises(InvalidConfigKeyError):
            e.set_value("invalid_key", "value")

        with pytest.raises(InvalidConfigValueTypeError):
            e.set_value("telemetry.mode", True)

        with pytest.raises(InvalidConfigValueTypeError):
            e.set_value("telemetry.mode", 1)

        with pytest.raises(ProtectedGlobalConfigError):
            e.set_value("installation.externally_managed", True)

        e.set_value("telemetry.mode", "off")
        e.stage()

    with open(temp_config_file, "rb") as fp:
        content = tomllib.load(fp)
    assert "installation" not in content
    assert content["telemetry"]["mode"] == "off"


def test_unset_value_remove_section(temp_config_file: pathlib.Path) -> None:
    with ConfigEditor(temp_config_file) as e:
        e.set_value("telemetry.mode", "off")
        e.set_value("repo.remote", "http://test.example.com")
        e.stage()

    with open(temp_config_file, "rb") as fp:
        content = tomllib.load(fp)
    assert content["repo"]["remote"] == "http://test.example.com"
    assert content["telemetry"]["mode"] == "off"

    with ConfigEditor(temp_config_file) as e:
        e.unset_value("telemetry.mode")
        e.remove_section("repo")
        e.stage()

        with pytest.raises(InvalidConfigSectionError):
            e.remove_section("foo")

    with open(temp_config_file, "rb") as fp:
        content = tomllib.load(fp)
    assert "repo" not in content
    assert "telemetry" in content
    assert "mode" not in content["telemetry"]


def test_malformed_config_file_error(temp_config_file: pathlib.Path) -> None:
    with open(temp_config_file, "wb") as fp:
        fp.write(b"repo = 1\n")

    with pytest.raises(MalformedConfigFileError):
        with ConfigEditor(temp_config_file) as e:
            e.set_value("repo.branch", "foo")
