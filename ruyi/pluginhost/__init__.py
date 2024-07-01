import pathlib
from typing import Self

import xingque

from . import api
from . import paths


class PluginHostContext:
    def __init__(self, plugin_root: pathlib.Path) -> None:
        self._plugin_root = plugin_root
        # resolved path: frozen module
        self._module_cache: dict[str, xingque.FrozenModule] = {}
        # plugin id: frozen plugin module
        self._loaded_plugins: dict[str, xingque.FrozenModule] = {}

    def load_plugin(self, plugin_id: str) -> None:
        plugin_dir = paths.get_plugin_dir(plugin_id, self._plugin_root)

        loader = Loader(
            self._plugin_root,
            plugin_dir / paths.PLUGIN_ENTRYPOINT_FILENAME,
            self._module_cache,
        )
        loaded_plugin = loader.load_this_plugin()
        self._loaded_plugins[plugin_id] = loaded_plugin

    def is_plugin_loaded(self, plugin_id: str) -> bool:
        return plugin_id in self._loaded_plugins

    def get_from_plugin(self, plugin_id: str, key: str) -> object | None:
        if not self.is_plugin_loaded(plugin_id):
            self.load_plugin(plugin_id)

        return self._loaded_plugins[plugin_id].get_option(key)


class Loader:
    """Starlark FileLoader loading from Ruyi repo.

    Load paths take one of the following shapes:

    * relative path: loads the path relative from the originating file's location,
      but crossing plugin boundary is not allowed
    * absolute path: similar to above, but relative to the plugin's Starlark root
    * `ruyi-plugin://${plugin-id}`: loads from the plugin `plugin-id` residing
      in the same repo as the originating plugin, the "entrypoint" being hard-coded
      as `mod.star`
    """

    def __init__(
        self,
        root: pathlib.Path,
        originating_file: pathlib.Path,
        module_cache: dict[str, xingque.FrozenModule],
    ) -> None:
        self.root = root
        self.originating_file = originating_file
        self.module_cache = module_cache

    def make_sub_loader(self, originating_file: pathlib.Path) -> Self:
        return self.__class__(
            self.root,
            originating_file,
            self.module_cache,
        )

    def load_this_plugin(self) -> xingque.FrozenModule:
        return self._load(str(self.originating_file), True)

    def load(self, path: str) -> xingque.FrozenModule:
        return self._load(path, False)

    def _load(self, path: str, is_root: bool) -> xingque.FrozenModule:
        resolved_path: pathlib.Path
        if is_root:
            resolved_path = pathlib.Path(path)
        else:
            resolved_path = paths.resolve_ruyi_load_path(
                path,
                self.root,
                False,
                self.originating_file,
            )
        resolved_path_str = str(resolved_path)
        if resolved_path_str in self.module_cache:
            return self.module_cache[resolved_path_str]

        plugin_id = resolved_path.relative_to(self.root).parts[0]
        plugin_dir = self.root / plugin_id

        gb = xingque.GlobalsBuilder.standard()
        gb.set(
            "ruyi_plugin_rev",
            api.make_ruyi_plugin_api_for_module(self.root, resolved_path, plugin_dir),
        )
        globals = gb.build()

        ast = xingque.AstModule.parse(resolved_path_str, resolved_path.read_text())
        m = xingque.Module()
        ev = xingque.Evaluator(m)
        ev.set_loader(self.make_sub_loader(resolved_path))
        ev.eval_module(ast, globals)
        fm = m.freeze()
        self.module_cache[resolved_path_str] = fm
        return fm

