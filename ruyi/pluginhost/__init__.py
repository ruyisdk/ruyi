import pathlib
import re
from typing import Self
from urllib.parse import unquote, urlparse

import xingque

from . import api


def get_plugin_entrypoint(plugin_id: str, plugin_root: pathlib.Path) -> pathlib.Path:
    validate_plugin_id(plugin_id)
    return plugin_root / plugin_id / "mod.star"


class PluginHostContext:
    def __init__(self, plugin_root: pathlib.Path) -> None:
        self._plugin_root = plugin_root
        # resolved path: frozen module
        self._module_cache: dict[str, xingque.FrozenModule] = {}
        # plugin id: frozen plugin module
        self._loaded_plugins: dict[str, xingque.FrozenModule] = {}

    def make_globals(self) -> xingque.Globals:
        gb = xingque.GlobalsBuilder.standard()
        gb.set("ruyi_plugin_rev", api.ruyi_plugin_rev)
        return gb.build()

    def load_plugin(self, plugin_id: str) -> None:
        loader = Loader(
            self.make_globals(),
            self._plugin_root,
            get_plugin_entrypoint(plugin_id, self._plugin_root),
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
        globals: xingque.Globals,
        root: pathlib.Path,
        originating_file: pathlib.Path,
        module_cache: dict[str, xingque.FrozenModule],
    ) -> None:
        self.globals = globals
        self.root = root
        self.originating_file = originating_file
        self.module_cache = module_cache

    def make_sub_loader(self, originating_file: pathlib.Path) -> Self:
        return self.__class__(
            self.globals,
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
            resolved_path = resolve_ruyi_load_path(
                path,
                self.root,
                self.originating_file,
            )
        resolved_path_str = str(resolved_path)
        if resolved_path_str in self.module_cache:
            return self.module_cache[resolved_path_str]

        ast = xingque.AstModule.parse(resolved_path_str, resolved_path.read_text())
        m = xingque.Module()
        ev = xingque.Evaluator(m)
        ev.set_loader(self.make_sub_loader(resolved_path))
        ev.eval_module(ast, self.globals)
        fm = m.freeze()
        self.module_cache[resolved_path_str] = fm
        return fm


def resolve_ruyi_load_path(
    path: str,
    plugin_root: pathlib.Path,
    originating_file: pathlib.Path,
) -> pathlib.Path:
    parsed = urlparse(path)
    if parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError("fancy URI features are not supported for load paths")

    match parsed.scheme:
        case "":
            if parsed.netloc:
                raise RuntimeError("'//' is not allowed as load path prefix")
            return resolve_plain_load_path(parsed.path, plugin_root, originating_file)

        case "ruyi-plugin":
            if parsed.path:
                raise RuntimeError(
                    "non-empty path segment is not allowed for ruyi-plugin:// load paths"
                )

            if not parsed.netloc:
                raise RuntimeError(
                    "empty location is not allowed for ruyi-plugin:// load paths"
                )

            plugin_id = unquote(parsed.netloc)
            validate_plugin_id(plugin_id)

            return plugin_root / plugin_id / "mod.star"

        case _:
            raise RuntimeError(
                f"unsupported Ruyi Starlark load path scheme {parsed.scheme}"
            )


def resolve_plain_load_path(
    path: str,
    plugin_root: pathlib.Path,
    originating_file: pathlib.Path,
) -> pathlib.Path:
    rel = originating_file.relative_to(plugin_root)
    plugin_dir = rel.parts[0]
    this_plugin_root = plugin_root / plugin_dir

    p = pathlib.PurePosixPath(path)
    if p.is_absolute():
        return this_plugin_root / p.relative_to("/")

    resolved = this_plugin_root / p
    if not resolved.is_relative_to(plugin_root):
        raise ValueError("plain load paths are not allowed to cross plugin boundary")

    return resolved


PLUGIN_ID_RE = re.compile("^[A-Za-z_][A-Za-z0-9_-]*$")


def validate_plugin_id(name: str) -> None:
    if PLUGIN_ID_RE.match(name) is None:
        raise RuntimeError(f"invalid plugin ID '{name}'")
