from contextlib import contextmanager, redirect_stderr, redirect_stdout
from importlib import resources
from dataclasses import dataclass
import io
import os
import pathlib
import sys
from typing import Generator, cast

from pygit2 import Repository
import pytest

from ruyi.cli.main import main as ruyi_main
from ruyi.config import GlobalConfig
from ruyi.log import RuyiConsoleLogger, RuyiLogger
from ruyi.ruyipkg.repo import MetadataRepo
from ruyi.utils.global_mode import EnvGlobalModeProvider, GlobalModeProvider


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


@dataclass
class CLIRunResult:
    exit_code: int
    stdout: str
    stderr: str


class MockRepository:
    def __init__(self, root: pathlib.Path) -> None:
        self.workdir = root
        self.path = root


class IntegrationTestHarness:
    def __init__(
        self,
        env: dict[str, str],
        repo_root: pathlib.Path,
        repo_url: str,
        repo_branch: str,
    ) -> None:
        self._env = env
        self.repo_root = repo_root
        self.repo_url = repo_url
        self.repo_branch = repo_branch

    def __call__(self, *args: str) -> CLIRunResult:
        return self.run(*args)

    def run(self, *args: str) -> CLIRunResult:
        argv = ["ruyi", *args]
        stdout_io = io.StringIO()
        stderr_io = io.StringIO()
        with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
            gm = EnvGlobalModeProvider(self._env, argv)
            gm.record_self_exe(argv[0], __file__, argv[0])
            logger = RuyiConsoleLogger(gm, stdout=stdout_io, stderr=stderr_io)
            gc = GlobalConfig.load_from_config(gm, logger)
            gc.override_repo_dir = str(self.repo_root)
            gc.override_repo_url = self.repo_url
            gc.override_repo_branch = self.repo_branch
            exit_code = ruyi_main(gm, gc, argv)
        return CLIRunResult(exit_code, stdout_io.getvalue(), stderr_io.getvalue())

    def add_package(
        self,
        category: str,
        name: str,
        version: str,
        manifest_toml: str,
    ) -> pathlib.Path:
        pkg_dir = self.repo_root / "manifests" / category / name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = pkg_dir / f"{version}.toml"
        manifest_path.write_text(manifest_toml, encoding="utf-8")
        return manifest_path


def _populate_default_packages_index(repo_root: pathlib.Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)

    config_text = """\
ruyi-repo = "v1"

[[mirrors]]
id = "ruyi-dist"
urls = ["https://example.invalid/dist/"]
"""

    (repo_root / "config.toml").write_text(config_text + "\n", encoding="utf-8")

    sha_stub = "0" * 64
    manifest_text = f"""\
format = "v1"
kind = ["source"]

[metadata]
desc = "Sample integration package"
vendor = {{ name = "Ruyi Integration Tests", eula = "" }}

[[distfiles]]
name = "sample-src.tar.zst"
size = 0

[distfiles.checksums]
sha256 = "{sha_stub}"
"""

    manifest_dir = repo_root / "manifests" / "dev-tools" / "sample-cli"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "1.0.0.toml").write_text(manifest_text + "\n", encoding="utf-8")


@pytest.fixture
def ruyi_cli_runner(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> IntegrationTestHarness:
    base_dir = tmp_path / "integration-env"
    home_dir = base_dir / "home"
    cache_dir = base_dir / "cache"
    config_dir = base_dir / "config"
    data_dir = base_dir / "data"
    state_dir = base_dir / "state"

    for p in (home_dir, cache_dir, config_dir, data_dir, state_dir):
        p.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_dir))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_dir))
    monkeypatch.setenv("RUYI_TELEMETRY_OPTOUT", "1")

    repo_root = cache_dir / "ruyi" / "packages-index"
    _populate_default_packages_index(repo_root)

    def _ensure_git_repo_stub(self: MetadataRepo) -> Repository:
        if self.repo is None:
            repo_path = pathlib.Path(self.root)
            repo_path.mkdir(parents=True, exist_ok=True)
            self.repo = cast(Repository, MockRepository(repo_path))
        return self.repo

    monkeypatch.setattr(MetadataRepo, "ensure_git_repo", _ensure_git_repo_stub)

    env = dict(os.environ)

    return IntegrationTestHarness(
        env=env,
        repo_root=repo_root,
        repo_url="https://example.invalid/packages-index.git",
        repo_branch="main",
    )
