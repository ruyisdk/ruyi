from contextlib import AbstractContextManager
from importlib import resources
import pathlib
import sys

import pytest

from ruyi.log import RuyiConsoleLogger, RuyiLogger
from ruyi.utils.global_mode import GlobalModeProvider


class RuyiFileFixtureFactory:
    def __init__(self, module: resources.Package | None = None) -> None:
        if sys.version_info < (3, 12):
            assert module is not None
        self.module = module

    def path(self, *frags: str) -> AbstractContextManager[pathlib.Path]:
        if sys.version_info < (3, 12):
            assert self.module is not None
        return resources.as_file(resources.files(self.module).joinpath(*frags))

    def plugin_suite(self, suite_name: str) -> AbstractContextManager[pathlib.Path]:
        if sys.version_info < (3, 12):
            assert self.module is not None
        path = resources.files(self.module)
        if sys.version_info >= (3, 11):
            path = path.joinpath("plugins_suites", suite_name)
        else:
            path = path.joinpath("plugins_suites")
            path = path.joinpath(suite_name)

        return resources.as_file(path)


class MockGlobalModeProvider(GlobalModeProvider):
    def __init__(
        self,
        is_debug: bool = False,
        is_experimental: bool = False,
        is_porcelain: bool = False,
        is_telemetry_optout: bool = False,
        venv_root: str | None = None,
    ) -> None:
        self._is_debug = is_debug
        self._is_experimental = is_experimental
        self._is_porcelain = is_porcelain
        self._is_telemetry_optout = is_telemetry_optout
        self._venv_root = venv_root

    @property
    def argv0(self) -> str:
        return "ruyi"

    @property
    def main_file(self) -> str:
        return "ruyi/__main__.py"

    @property
    def self_exe(self) -> str:
        return "ruyi"

    @property
    def is_debug(self) -> bool:
        return self._is_debug

    @property
    def is_experimental(self) -> bool:
        return self._is_experimental

    @property
    def is_packaged(self) -> bool:
        return False

    @property
    def is_porcelain(self) -> bool:
        return self._is_porcelain

    @is_porcelain.setter
    def is_porcelain(self, v: bool) -> None:
        self._is_porcelain = v

    @property
    def is_telemetry_optout(self) -> bool:
        return self._is_telemetry_optout

    @property
    def venv_root(self) -> str | None:
        return self._venv_root


@pytest.fixture
def ruyi_file() -> RuyiFileFixtureFactory:
    return RuyiFileFixtureFactory(None if sys.version_info >= (3, 12) else __name__)


@pytest.fixture
def mock_gm() -> MockGlobalModeProvider:
    return MockGlobalModeProvider()


@pytest.fixture
def ruyi_logger(mock_gm: GlobalModeProvider) -> RuyiLogger:
    """Fixture for creating a RuyiLogger instance."""
    return RuyiConsoleLogger(mock_gm)
