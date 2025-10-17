import abc
import os
from typing import Final, Mapping, Protocol, runtime_checkable

import ruyi

ENV_DEBUG: Final = "RUYI_DEBUG"
ENV_EXPERIMENTAL: Final = "RUYI_EXPERIMENTAL"
ENV_FORCE_ALLOW_ROOT: Final = "RUYI_FORCE_ALLOW_ROOT"
ENV_TELEMETRY_OPTOUT_KEY: Final = "RUYI_TELEMETRY_OPTOUT"
ENV_VENV_ROOT_KEY: Final = "RUYI_VENV"

TRUTHY_ENV_VAR_VALUES: Final = {"1", "true", "x", "y", "yes"}


def is_env_var_truthy(env: Mapping[str, str], var: str) -> bool:
    if v := env.get(var):
        return v.lower() in TRUTHY_ENV_VAR_VALUES
    return False


@runtime_checkable
class ProvidesGlobalMode(Protocol):
    @property
    def argv0(self) -> str: ...

    @property
    def main_file(self) -> str: ...

    @property
    def self_exe(self) -> str: ...

    @property
    def is_debug(self) -> bool: ...

    @property
    def is_experimental(self) -> bool: ...

    @property
    def is_packaged(self) -> bool: ...

    @property
    def is_porcelain(self) -> bool: ...

    @property
    def is_telemetry_optout(self) -> bool: ...

    @property
    def is_cli_autocomplete(self) -> bool: ...

    @property
    def venv_root(self) -> str | None: ...


class GlobalModeProvider(metaclass=abc.ABCMeta):
    """
    Abstract base class for global mode providers.
    """

    @property
    @abc.abstractmethod
    def argv0(self) -> str:
        return ""

    @property
    @abc.abstractmethod
    def main_file(self) -> str:
        return ""

    @property
    @abc.abstractmethod
    def self_exe(self) -> str:
        return ""

    def record_self_exe(self, argv0: str, main_file: str, self_exe: str) -> None:
        pass

    @property
    @abc.abstractmethod
    def is_debug(self) -> bool:
        return False

    @property
    @abc.abstractmethod
    def is_experimental(self) -> bool:
        return False

    @property
    @abc.abstractmethod
    def is_packaged(self) -> bool:
        return False

    @property
    @abc.abstractmethod
    def is_porcelain(self) -> bool:
        return False

    @is_porcelain.setter
    @abc.abstractmethod
    def is_porcelain(self, v: bool) -> None:
        pass

    @property
    @abc.abstractmethod
    def is_telemetry_optout(self) -> bool:
        return False

    @property
    @abc.abstractmethod
    def is_cli_autocomplete(self) -> bool:
        return False

    @property
    @abc.abstractmethod
    def venv_root(self) -> str | None:
        return None


def _guess_porcelain_from_argv(argv: list[str]) -> bool:
    """
    Guess if the current invocation is a "porcelain" command based on the
    arguments passed, without requiring the ``argparse`` machinery to be
    completely initialized.
    """
    # If the first argument is `--porcelain`, we assume it's a porcelain command.
    # This is currently accurate as the porcelain flag is only possible at this
    # position right now.
    return len(argv) > 1 and argv[1] == "--porcelain"


def _probe_cli_autocomplete(env: Mapping[str, str], argv: list[str]) -> bool:
    """
    Probe if the current invocation is related to shell completion based on
    the arguments passed, without requiring the ``argparse`` machinery to be
    completely initialized, and the environment.
    """

    # If `--output-completion-script` is present anywhere in the arguments,
    # then this is related to shell completion even if _ARGCOMPLETE is not yet
    # set (which is only set for invocations after the shell finished sourcing
    # the completion script).
    for arg in argv:
        if arg.startswith("--output-completion-script"):
            return True

    return "_ARGCOMPLETE" in env


class EnvGlobalModeProvider(GlobalModeProvider):
    def __init__(
        self,
        env: Mapping[str, str] | None = None,
        argv: list[str] | None = None,
    ) -> None:
        if env is None:
            env = os.environ
        if argv is None:
            argv = []

        self._argv0 = ""
        self._main_file = ""
        self._self_exe = ""

        self._is_debug = is_env_var_truthy(env, ENV_DEBUG)
        self._is_experimental = is_env_var_truthy(env, ENV_EXPERIMENTAL)
        self._is_porcelain = _guess_porcelain_from_argv(argv)
        self._is_telemetry_optout = is_env_var_truthy(env, ENV_TELEMETRY_OPTOUT_KEY)

        # We have to lift this piece of implementation detail out of argcomplete,
        # as the argcomplete import is very costly in terms of startup time.
        self._is_cli_autocomplete = _probe_cli_autocomplete(env, argv)

        self._venv_root = env.get(ENV_VENV_ROOT_KEY)

    @property
    def argv0(self) -> str:
        return self._argv0

    @property
    def main_file(self) -> str:
        return self._main_file

    @property
    def self_exe(self) -> str:
        return self._self_exe

    def record_self_exe(self, argv0: str, main_file: str, self_exe: str) -> None:
        self._argv0 = argv0
        self._main_file = main_file
        self._self_exe = self_exe

    @property
    def is_debug(self) -> bool:
        return self._is_debug

    @property
    def is_experimental(self) -> bool:
        return self._is_experimental

    @property
    def is_packaged(self) -> bool:
        return hasattr(ruyi, "__compiled__")

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
