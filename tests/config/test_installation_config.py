"""Tests for [installation] config section parsing and protection."""

from typing import TYPE_CHECKING

from ruyi.config import GlobalConfig

if TYPE_CHECKING:
    from tests.fixtures import MockGlobalModeProvider
    from ruyi.log import RuyiLogger


class TestInstallationConfig:
    def test_defaults(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        assert gc.is_installation_externally_managed is False
        assert gc.is_installation_oobe_disabled is False
        assert gc.is_installation_telemetry_disabled_by_default is False

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

    def test_global_scope_sets_disable_oobe(
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
        assert gc.is_installation_oobe_disabled is True

    def test_global_scope_sets_disable_telemetry_by_default(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "disable_telemetry_by_default": True,
                }
            },
            is_global_scope=True,
        )
        assert gc.is_installation_telemetry_disabled_by_default is True

    def test_global_scope_falsey_values(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "disable_oobe": False,
                    "disable_telemetry_by_default": False,
                }
            },
            is_global_scope=True,
        )
        assert gc.is_installation_oobe_disabled is False
        assert gc.is_installation_telemetry_disabled_by_default is False


class TestTelemetryDefaultBehavior:
    def test_default_telemetry_mode_is_local(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        assert gc.telemetry_mode == "local"

    def test_disable_telemetry_by_default_sets_mode_to_off(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "disable_telemetry_by_default": True,
                }
            },
            is_global_scope=True,
        )
        assert gc.telemetry_mode == "off"

    def test_flag_ignored_when_telemetry_mode_is_explicit(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "disable_telemetry_by_default": True,
                }
            },
            is_global_scope=True,
        )
        gc.telemetry_mode = "local"
        assert gc.telemetry_mode == "local"

    def test_flag_ignored_in_user_scope(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "disable_telemetry_by_default": True,
                }
            },
            is_global_scope=False,
        )
        assert gc.is_installation_telemetry_disabled_by_default is False
        assert gc.telemetry_mode == "local"

    def test_disable_telemetry_by_default_does_not_affect_explicit_on(
        self,
        mock_gm: "MockGlobalModeProvider",
        ruyi_logger: "RuyiLogger",
    ) -> None:
        gc = GlobalConfig(mock_gm, ruyi_logger)
        gc._apply_config(
            {
                "installation": {
                    "disable_telemetry_by_default": True,
                }
            },
            is_global_scope=True,
        )
        gc.telemetry_mode = "on"
        assert gc.telemetry_mode == "on"
