import abc
import enum
from functools import cached_property
import os
import pathlib
from typing import (
    Callable,
    Final,
    Generic,
    MutableMapping,
    TypeVar,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from typing_extensions import Self

from ..log import RuyiLogger
from . import api
from . import paths
from .build_api import ScheduledBuild
from .traits import SupportsEvalFunction, SupportsGetOption, SupportsMessageStore


ENV_PLUGIN_BACKEND_KEY: Final = "RUYI_PLUGIN_BACKEND"


class PluginLoadMode(enum.Enum):
    """The context in which a Starlark module is being loaded.

    The mode controls which host API surfaces are exposed to the loaded
    module and what file system accesses are permitted.

    * ``PACKAGE_PLUGIN``: an ordinary plugin shipped inside a packages-index
      repository (profile plugins, device-provisioner strategies, ...).
      These have no access to the host filesystem outside of their plugin
      directory.
    * ``COMMAND_PLUGIN``: a ``ruyi-cmd-*`` plugin implementing a user-facing
      ``ruyi`` subcommand. Allowed to reach into the host filesystem via
      the ``host://`` load path scheme.
    * ``BUILD_RECIPE``: a ``ruyi admin build-package`` recipe. Rooted at a
      ``ruyi-build-recipes.toml`` project root; may register scheduled
      builds but has no host-FS access through load paths.
    """

    PACKAGE_PLUGIN = "package-plugin"
    COMMAND_PLUGIN = "command-plugin"
    BUILD_RECIPE = "build-recipe"

    @property
    def allow_host_fs_access(self) -> bool:
        return self is PluginLoadMode.COMMAND_PLUGIN


ModuleTy = TypeVar("ModuleTy", bound=SupportsGetOption, covariant=True)
EvalTy = TypeVar("EvalTy", bound=SupportsEvalFunction, covariant=True)


class PluginHostContext(Generic[ModuleTy, EvalTy], metaclass=abc.ABCMeta):
    @staticmethod
    def new(
        host_logger: RuyiLogger,
        plugin_root: pathlib.Path,
        *,
        locale: str | None = None,
        message_store_factory: Callable[[], SupportsMessageStore] | None = None,
        recipe_project_root: pathlib.Path | None = None,
    ) -> "PluginHostContext[SupportsGetOption, SupportsEvalFunction]":
        plugin_backend = os.environ.get("RUYI_PLUGIN_BACKEND", "")
        if not plugin_backend:
            plugin_backend = "unsandboxed"

        match plugin_backend:
            case "unsandboxed":
                return UnsandboxedPluginHostContext(
                    host_logger,
                    plugin_root,
                    locale=locale,
                    message_store_factory=message_store_factory,
                    recipe_project_root=recipe_project_root,
                )
            case _:
                raise RuntimeError(f"unsupported plugin backend: {plugin_backend}")

    def __init__(
        self,
        host_logger: RuyiLogger,
        plugin_root: pathlib.Path,
        *,
        locale: str | None = None,
        message_store_factory: Callable[[], SupportsMessageStore] | None = None,
        recipe_project_root: pathlib.Path | None = None,
    ) -> None:
        self._host_logger = host_logger
        self._plugin_root = plugin_root
        # resolved path: finalized module
        self._module_cache: MutableMapping[str, ModuleTy] = {}
        # plugin id: finalized plugin module
        self._loaded_plugins: dict[str, SupportsGetOption] = {}
        # plugin id: {key: value}
        self._value_cache: dict[str, dict[str, object]] = {}

        self._locale = locale or ""
        self._msg_store_factory = message_store_factory
        self._recipe_project_root = recipe_project_root

        capabilities: set[str] = {"call-subprocess-v1"}
        if self.has_i18n_capability():
            # Expose the i18n-v1 feature only if the host context is properly
            # configured for it
            capabilities.add("i18n-v1")
        if recipe_project_root is not None:
            capabilities.add("build-recipe-v1")
            capabilities.discard("call-subprocess-v1")
        self._capabilities: frozenset[str] = frozenset(capabilities)

        # Scheduled builds, populated by RUYI.build.schedule_build during
        # load of a build-recipe module. Keyed by recipe file path.
        self._scheduled_builds: dict[pathlib.Path, list["ScheduledBuild"]] = {}

    @abc.abstractmethod
    def make_loader(
        self,
        originating_file: pathlib.Path,
        module_cache: MutableMapping[str, ModuleTy],
        load_mode: PluginLoadMode,
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

    @property
    def recipe_project_root(self) -> pathlib.Path | None:
        return self._recipe_project_root

    def scheduled_builds_for(
        self,
        recipe_file: pathlib.Path,
    ) -> list[ScheduledBuild]:
        """Return (creating if needed) the scheduled-build registry for
        the given recipe file. Shared by all ``RUYI.build.schedule_build``
        calls within the same module load.
        """

        return self._scheduled_builds.setdefault(recipe_file, [])

    def all_scheduled_builds(self) -> dict[pathlib.Path, list[ScheduledBuild]]:
        return self._scheduled_builds

    def load_plugin(self, plugin_id: str, load_mode: PluginLoadMode) -> None:
        plugin_dir = paths.get_plugin_dir(plugin_id, self._plugin_root)

        loader = self.make_loader(
            plugin_dir / paths.PLUGIN_ENTRYPOINT_FILENAME,
            self._module_cache,
            load_mode,
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
            load_mode = (
                PluginLoadMode.COMMAND_PLUGIN
                if is_cmd_plugin
                else PluginLoadMode.PACKAGE_PLUGIN
            )
            self.load_plugin(plugin_id, load_mode)

        if plugin_id not in self._value_cache:
            self._value_cache[plugin_id] = {}

        try:
            return self._value_cache[plugin_id][key]
        except KeyError:
            v = self._loaded_plugins[plugin_id].get_option(key)
            self._value_cache[plugin_id][key] = v
            return v

    def has_i18n_capability(self) -> bool:
        return self._msg_store_factory is not None

    @property
    def capabilities(self) -> frozenset[str]:
        return self._capabilities

    @property
    def locale(self) -> str:
        return self._locale

    @cached_property
    def message_store(self) -> SupportsMessageStore | None:
        if self._msg_store_factory is None:
            return None
        return self._msg_store_factory()


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
        load_mode: PluginLoadMode,
    ) -> None:
        self._phctx = phctx
        self.originating_file = originating_file
        self.module_cache = module_cache
        self.load_mode = load_mode

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
            self.load_mode,
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
                self.load_mode.allow_host_fs_access,
                recipe_project_root=self._phctx.recipe_project_root,
            )
        resolved_path_str = str(resolved_path)
        if resolved_path_str in self.module_cache:
            return self.module_cache[resolved_path_str]

        if self.load_mode is PluginLoadMode.BUILD_RECIPE:
            recipe_root = self._phctx.recipe_project_root
            if recipe_root is None:
                raise RuntimeError(
                    "BUILD_RECIPE load mode requires a recipe_project_root on "
                    "the host context"
                )
            plugin_dir = recipe_root
        else:
            plugin_id = resolved_path.relative_to(self.root).parts[0]
            plugin_dir = self.root / plugin_id

        host_bridge = api.make_ruyi_plugin_api_for_module(
            self._phctx,
            resolved_path,
            plugin_dir,
            self.load_mode,
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
