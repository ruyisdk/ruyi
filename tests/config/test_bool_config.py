"""Tests for validation of boolean config values loaded from TOML."""

from typing import Any, cast, TYPE_CHECKING

from ruyi.config import GlobalConfig

if TYPE_CHECKING:
    from tests.fixtures import MockGlobalModeProvider
    from ruyi.log import RuyiLogger


def test_quoted_boolean_value_is_ignored(
    mock_gm: "MockGlobalModeProvider",
    ruyi_logger: "RuyiLogger",
) -> None:
    gc = GlobalConfig(mock_gm, ruyi_logger)
    gc._apply_config(
        # Deliberately malformed: this would have been truthy under bool().
        cast(Any, {"repo": {"disabled": "false"}}),
        is_global_scope=False,
    )
    if "repo_entries" in gc.__dict__:
        del gc.__dict__["repo_entries"]

    assert gc.repo_entries[0].active is True
