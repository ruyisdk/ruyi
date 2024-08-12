import pathlib
import tomllib
from typing import Any, Callable

from ruyi import log
from ruyi.cli import user_input
from ruyi.cli.version import RUYI_SEMVER
from .paths import resolve_ruyi_load_path


class RuyiHostAPI:
    def __init__(
        self,
        plugin_root: pathlib.Path,
        this_file: pathlib.Path,
        this_plugin_dir: pathlib.Path,
    ) -> None:
        self._plugin_root = plugin_root
        self._this_file = this_file
        self._this_plugin_dir = this_plugin_dir

        self._logger = RuyiPluginLogger()

    @property
    def ruyi_version(self) -> str:
        return str(RUYI_SEMVER)

    @property
    def ruyi_plugin_api_rev(self) -> int:
        return 1

    def load_toml(self, path: str) -> object:
        resolved_path = resolve_ruyi_load_path(
            path,
            self._plugin_root,
            True,
            self._this_file,
        )
        with open(resolved_path, "rb") as f:
            return tomllib.load(f)

    @property
    def log(self) -> "RuyiPluginLogger":
        return self._logger

    def cli_ask_for_choice(self, prompt: str, choice_texts: list[str]) -> int:
        return user_input.ask_for_choice(prompt, choice_texts)

    def cli_ask_for_file(self, prompt: str) -> str:
        return user_input.ask_for_file(prompt)

    def cli_ask_for_kv_choice(self, prompt: str, choices_kv: dict[str, str]) -> str:
        return user_input.ask_for_kv_choice(prompt, choices_kv)

    def cli_ask_for_yesno_confirmation(
        self,
        prompt: str,
        default: bool = False,
    ) -> bool:
        return user_input.ask_for_yesno_confirmation(prompt, default)


class RuyiPluginLogger:
    def __init__(self) -> None:
        pass

    def stdout(
        self,
        message: str,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        log.stdout(message, *objects, sep=sep, end=end)

    def D(
        self,
        message: str,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        log.D(message, *objects, sep=sep, end=end, _stack_offset_delta=1)

    def W(
        self,
        message: str,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        log.W(message, *objects, sep=sep, end=end)

    def I(  # noqa: E743 # the name intentionally mimics Android logging for brevity
        self,
        message: str,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        log.I(message, *objects, sep=sep, end=end)

    def F(
        self,
        message: str,
        *objects: Any,
        sep: str = " ",
        end: str = "\n",
    ) -> None:
        log.F(message, *objects, sep=sep, end=end)


def _ruyi_plugin_rev(
    plugin_root: pathlib.Path,
    this_file: pathlib.Path,
    this_plugin_dir: pathlib.Path,
    rev: object,
) -> RuyiHostAPI:
    if not isinstance(rev, int):
        raise TypeError("rev must be int in ruyi_plugin_rev calls")
    if rev != 1:
        raise ValueError(
            f"Ruyi plugin API revision {rev} is not supported by this Ruyi"
        )
    return RuyiHostAPI(plugin_root, this_file, this_plugin_dir)


def make_ruyi_plugin_api_for_module(
    plugin_root: pathlib.Path,
    this_file: pathlib.Path,
    this_plugin_dir: pathlib.Path,
) -> Callable[[object], RuyiHostAPI]:
    return lambda rev: _ruyi_plugin_rev(plugin_root, this_file, this_plugin_dir, rev)
