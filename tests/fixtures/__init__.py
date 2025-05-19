from contextlib import AbstractContextManager
from importlib import resources
import pathlib
import sys

import pytest

from ruyi.log import RuyiConsoleLogger, RuyiLogger


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


@pytest.fixture
def ruyi_file() -> RuyiFileFixtureFactory:
    return RuyiFileFixtureFactory(None if sys.version_info >= (3, 12) else __name__)


@pytest.fixture
def ruyi_logger() -> RuyiLogger:
    """Fixture for creating a RuyiLogger instance."""
    return RuyiConsoleLogger()
