from contextlib import contextmanager
from importlib import resources
import pathlib
import sys
from typing import Generator

import pytest

from ruyi.log import RuyiConsoleLogger, RuyiLogger
from ruyi.utils.global_mode import GlobalModeProvider


class RuyiFileFixtureFactory:
    def __init__(self, module: resources.Package | None = None) -> None:
        self._fixtures_dir: pathlib.Path | None = None

        if sys.version_info < (3, 12):
            assert module is not None
        # Figure out the fixtures path in a compatible way
        if module is None:
            # Python 3.12+ fallback - get the directory of this file
            self._fixtures_dir = pathlib.Path(__file__).parent
        elif isinstance(module, str):
            # Import the module and get its path
            import importlib

            mod = importlib.import_module(module)
            if mod.__file__ is not None:
                self._fixtures_dir = pathlib.Path(mod.__file__).parent
            else:
                self._fixtures_dir = pathlib.Path(__file__).parent
        else:
            self.module = module

    @contextmanager
    def path(self, *frags: str) -> Generator[pathlib.Path, None, None]:
        if self._fixtures_dir is not None:
            # directly derive the file path for better compatibility
            result_path = self._fixtures_dir
            for frag in frags:
                result_path = result_path / frag
            yield result_path
            return

        # fallback to importlib.resources
        try:
            path = resources.files(self.module)
            for frag in frags:
                path = path.joinpath(frag)
            with resources.as_file(path) as p:
                yield p
                return
        except (TypeError, FileNotFoundError):
            pass

        # final fallback - use the directory of this file
        result_path = pathlib.Path(__file__).parent
        for frag in frags:
            result_path = result_path / frag
        yield result_path

    @contextmanager
    def plugin_suite(self, suite_name: str) -> Generator[pathlib.Path, None, None]:
        if self._fixtures_dir is not None:
            # directly derive the file path for better compatibility
            result_path = self._fixtures_dir / "plugins_suites" / suite_name
            yield result_path
            return

        # fallback to importlib.resources
        try:
            path = resources.files(self.module)
            path = path.joinpath("plugins_suites").joinpath(suite_name)
            with resources.as_file(path) as p:
                yield p
                return
        except (TypeError, FileNotFoundError):
            pass

        # final fallback - use the directory of this file
        result_path = pathlib.Path(__file__).parent / "plugins_suites" / suite_name
        yield result_path


class MockGlobalModeProvider(GlobalModeProvider):
    def __init__(
        self,
        is_debug: bool = False,
        is_experimental: bool = False,
        is_porcelain: bool = False,
        is_telemetry_optout: bool = False,
        is_cli_autocomplete: bool = False,
        venv_root: str | None = None,
    ) -> None:
        self._is_debug = is_debug
        self._is_experimental = is_experimental
        self._is_porcelain = is_porcelain
        self._is_telemetry_optout = is_telemetry_optout
        self._is_cli_autocomplete = is_cli_autocomplete
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
    def is_cli_autocomplete(self) -> bool:
        return self._is_cli_autocomplete

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
