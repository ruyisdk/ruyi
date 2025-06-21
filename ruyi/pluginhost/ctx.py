import abc
import os
import pathlib
from typing import (
    Callable,
    Final,
    Generic,
    MutableMapping,
    Protocol,
    TypeVar,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from typing_extensions import Self

from ..log import RuyiLogger
from . import api
from . import paths


ENV_PLUGIN_BACKEND_KEY: Final = "RUYI_PLUGIN_BACKEND"


class SupportsGetOption(Protocol):
    def get_option(self, key: str) -> object: ...


class SupportsEvalFunction(Protocol):
    def eval_function(
        self,
        function: object,
        *args: object,
        **kwargs: object,
    ) -> object: ...


ModuleTy = TypeVar("ModuleTy", bound=SupportsGetOption, covariant=True)
EvalTy = TypeVar("EvalTy", bound=SupportsEvalFunction, covariant=True)


class PluginHostContext(Generic[ModuleTy, EvalTy], metaclass=abc.ABCMeta):
    @staticmethod
    def new(
        host_logger: RuyiLogger,
        plugin_root: pathlib.Path,
    ) -> "PluginHostContext[SupportsGetOption, SupportsEvalFunction]":
        plugin_backend = os.environ.get("RUYI_PLUGIN_BACKEND", "")
        if not plugin_backend:
            plugin_backend = "unsandboxed"

        match plugin_backend:
            case "unsandboxed":
                return UnsandboxedPluginHostContext(host_logger, plugin_root)
            case _:
                raise RuntimeError(f"unsupported plugin backend: {plugin_backend}")

    def __init__(
        self,
        host_logger: RuyiLogger,
        plugin_root: pathlib.Path,
    ) -> None:
        self._host_logger = host_logger
        self._plugin_root = plugin_root
        # resolved path: finalized module
        self._module_cache: MutableMapping[str, ModuleTy] = {}
        # plugin id: finalized plugin module
        self._loaded_plugins: dict[str, SupportsGetOption] = {}
        # plugin id: {key: value}
        self._value_cache: dict[str, dict[str, object]] = {}

    @abc.abstractmethod
    def make_loader(
        self,
        originating_file: pathlib.Path,
        module_cache: MutableMapping[str, ModuleTy],
        is_cmd: bool,
    ) -> "BasePluginLoader[ModuleTy]":
        raise NotImplementedError

    @abc.abstractmethod
    def make_evaluator(self) -> EvalTy:
        raise NotImplementedError

    @property
    def host_logger(self) -> RuyiLogger:
        return self._host_logger

    @property
    def plugin_root(self) -> pathlib.Path:
        return self._plugin_root

    def load_plugin(self, plugin_id: str, is_cmd: bool) -> None:
        plugin_dir = paths.get_plugin_dir(plugin_id, self._plugin_root)

        loader = self.make_loader(
            plugin_dir / paths.PLUGIN_ENTRYPOINT_FILENAME,
            self._module_cache,
            is_cmd,
        )
        loaded_plugin = loader.load_this_plugin()
        self._loaded_plugins[plugin_id] = loaded_plugin

    def is_plugin_loaded(self, plugin_id: str) -> bool:
        return plugin_id in self._loaded_plugins

    def get_from_plugin(
        self,
        plugin_id: str,
        key: str,
        is_cmd_plugin: bool = False,
    ) -> object | None:
        if not self.is_plugin_loaded(plugin_id):
            self.load_plugin(plugin_id, is_cmd_plugin)

        if plugin_id not in self._value_cache:
            self._value_cache[plugin_id] = {}

        try:
            return self._value_cache[plugin_id][key]
        except KeyError:
            v = self._loaded_plugins[plugin_id].get_option(key)
            self._value_cache[plugin_id][key] = v
            return v


class BasePluginLoader(Generic[ModuleTy], metaclass=abc.ABCMeta):
    """Base class for plugin loaders loading from Ruyi repo.

    Load paths take one of the following shapes:

    * relative path: loads the path relative from the originating file's location,
      but crossing plugin boundary is not allowed
    * absolute path: similar to above, but relative to the plugin's FS root
    * `ruyi-plugin://${plugin-id}`: loads from the plugin `plugin-id` residing
      in the same repo as the originating plugin, the "entrypoint" being hard-coded
      to whatever the concrete implementation dictates
    """

    def __init__(
        self,
        phctx: PluginHostContext[ModuleTy, SupportsEvalFunction],
        originating_file: pathlib.Path,
        module_cache: MutableMapping[str, ModuleTy],
        is_cmd: bool,
    ) -> None:
        self._phctx = phctx
        self.originating_file = originating_file
        self.module_cache = module_cache
        self.is_cmd = is_cmd

    @property
    def host_logger(self) -> RuyiLogger:
        return self._phctx.host_logger

    @property
    def root(self) -> pathlib.Path:
        return self._phctx.plugin_root

    def make_sub_loader(self, originating_file: pathlib.Path) -> "Self":
        return self.__class__(
            self._phctx,
            originating_file,
            self.module_cache,
            self.is_cmd,
        )

    def load_this_plugin(self) -> ModuleTy:
        return self._load(str(self.originating_file), True)

    def load(self, path: str) -> ModuleTy:
        return self._load(path, False)

    def _load(self, path: str, is_root: bool) -> ModuleTy:
        resolved_path: pathlib.Path
        if is_root:
            resolved_path = pathlib.Path(path)
        else:
            resolved_path = paths.resolve_ruyi_load_path(
                path,
                self.root,
                False,
                self.originating_file,
                self.is_cmd,
            )
        resolved_path_str = str(resolved_path)
        if resolved_path_str in self.module_cache:
            return self.module_cache[resolved_path_str]

        plugin_id = resolved_path.relative_to(self.root).parts[0]
        plugin_dir = self.root / plugin_id

        host_bridge = api.make_ruyi_plugin_api_for_module(
            self._phctx,
            resolved_path,
            plugin_dir,
            self.is_cmd,
        )

        mod = self.do_load_module(
            resolved_path,
            resolved_path.read_text("utf-8"),
            host_bridge,
        )
        self.module_cache[resolved_path_str] = mod
        return mod

    @abc.abstractmethod
    def do_load_module(
        self,
        resolved_path: pathlib.Path,
        program: str,
        ruyi_host_bridge: Callable[[object], api.RuyiHostAPI],
    ) -> ModuleTy:
        raise NotImplementedError


# import the built-in supported PluginHostContext implementation(s)
# this must come after the baseclass declarations

# pylint: disable-next=wrong-import-position
from .unsandboxed import UnsandboxedPluginHostContext  # noqa: E402
