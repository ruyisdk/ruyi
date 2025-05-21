import abc
import os
from typing import Final, Mapping, Protocol, runtime_checkable

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
    def is_debug(self) -> bool: ...

    @property
    def is_experimental(self) -> bool: ...

    @property
    def is_porcelain(self) -> bool: ...

    @property
    def is_telemetry_optout(self) -> bool: ...

    @property
    def venv_root(self) -> str | None: ...


class GlobalModeProvider(metaclass=abc.ABCMeta):
    """
    Abstract base class for global mode providers.
    """

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
    def venv_root(self) -> str | None:
        return None


class EnvGlobalModeProvider(GlobalModeProvider):
    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        if env is None:
            env = os.environ

        self._is_debug = is_env_var_truthy(env, ENV_DEBUG)
        self._is_experimental = is_env_var_truthy(env, ENV_EXPERIMENTAL)
        self._is_porcelain = False  # this has to be initialized later
        self._is_telemetry_optout = is_env_var_truthy(env, ENV_TELEMETRY_OPTOUT_KEY)
        self._venv_root = env.get(ENV_VENV_ROOT_KEY)

    @property
    def is_debug(self) -> bool:
        return self._is_debug

    @property
    def is_experimental(self) -> bool:
        return self._is_experimental

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
