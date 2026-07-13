"""Tests for [installation] config section parsing and protection."""

from typing import TYPE_CHECKING

from ruyi.config import GlobalConfig

if TYPE_CHECKING:
    from tests.fixtures import MockGlobalModeProvider
    from ruyi.log import RuyiLogger


class TestInstallationConfig:
    def test_default_externally_managed_is_false(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        assert gc.is_installation_externally_managed is False

    def test_global_scope_sets_externally_managed(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "externally_managed": True,
                }
            },
            is_global_scope=True,
        )
        assert gc.is_installation_externally_managed is True

    def test_global_scope_externally_managed_falsey(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "externally_managed": False,
                }
            },
            is_global_scope=True,
        )
        assert gc.is_installation_externally_managed is False

    def test_global_scope_installation_section_without_externally_managed(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "disable_oobe": True,
                }
            },
            is_global_scope=True,
        )
        assert gc.is_installation_externally_managed is False

    def test_user_scope_rejects_installation_section(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "externally_managed": True,
                }
            },
            is_global_scope=False,
        )
        assert gc.is_installation_externally_managed is False

    def test_user_scope_installation_stays_default_regardless_of_value(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "externally_managed": False,
                }
            },
            is_global_scope=False,
        )
        assert gc.is_installation_externally_managed is False

    def test_global_scope_overrides_user_scope(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "externally_managed": True,
                }
            },
            is_global_scope=False,
        )
        assert gc.is_installation_externally_managed is False

        gc._apply_config(
            {
                "installation": {
                    "externally_managed": True,
                }
            },
            is_global_scope=True,
        )
        assert gc.is_installation_externally_managed is True
