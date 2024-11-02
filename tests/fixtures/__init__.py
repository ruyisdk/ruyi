from contextlib import AbstractContextManager
from importlib import resources
import pathlib

import pytest


class RuyiFileFixtureFactory:
    def __init__(self, module: resources.Package | None = None) -> None:
        self.module = module

    def path(self, *frags: str) -> AbstractContextManager[pathlib.Path]:
        return resources.as_file(resources.files(self.module).joinpath(*frags))

    def plugin_suite(self, suite_name: str) -> AbstractContextManager[pathlib.Path]:
        path = resources.files(self.module).joinpath("plugins_suites", suite_name)
        return resources.as_file(path)


@pytest.fixture
def ruyi_file() -> RuyiFileFixtureFactory:
    return RuyiFileFixtureFactory(None)
