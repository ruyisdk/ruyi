import pathlib
import re
from typing import Self
from urllib.parse import unquote, urlparse

import xingque

from . import api

PLUGIN_ENTRYPOINT_FILENAME = "mod.star"
PLUGIN_DATA_DIR = "data"


def get_plugin_dir(plugin_id: str, plugin_root: pathlib.Path) -> pathlib.Path:
    validate_plugin_id(plugin_id)
    return plugin_root / plugin_id


class PluginHostContext:
    def __init__(self, plugin_root: pathlib.Path) -> None:
        self._plugin_root = plugin_root
        # resolved path: frozen module
        self._module_cache: dict[str, xingque.FrozenModule] = {}
        # plugin id: frozen plugin module
        self._loaded_plugins: dict[str, xingque.FrozenModule] = {}

    def load_plugin(self, plugin_id: str) -> None:
        plugin_dir = get_plugin_dir(plugin_id, self._plugin_root)

        loader = Loader(
            self._plugin_root,
            plugin_dir / PLUGIN_ENTRYPOINT_FILENAME,
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
            resolved_path = resolve_ruyi_load_path(
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


def resolve_ruyi_load_path(
    path: str,
    plugin_root: pathlib.Path,
    is_for_data: bool,
    originating_file: pathlib.Path,
) -> pathlib.Path:
    parsed = urlparse(path)
    if parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError("fancy URI features are not supported for load paths")

    match parsed.scheme:
        case "":
            if parsed.netloc:
                raise RuntimeError("'//' is not allowed as load path prefix")
            return resolve_plain_load_path(
                parsed.path,
                plugin_root,
                is_for_data,
                originating_file=originating_file,
            )

        case "ruyi-plugin":
            if is_for_data:
                raise RuntimeError(
                    "the ruyi-plugin protocol is not allowed in this context"
                )

            if parsed.path:
                raise RuntimeError(
                    "non-empty path segment is not allowed for ruyi-plugin:// load paths"
                )

            if not parsed.netloc:
                raise RuntimeError(
                    "empty location is not allowed for ruyi-plugin:// load paths"
                )

            plugin_id = unquote(parsed.netloc)
            return get_plugin_dir(plugin_id, plugin_root) / PLUGIN_ENTRYPOINT_FILENAME

        case "ruyi-plugin-data":
            if not is_for_data:
                raise RuntimeError(
                    "the ruyi-plugin-data protocol is not allowed in this context"
                )

            if not parsed.path:
                raise RuntimeError(
                    "empty path segment is not allowed for ruyi-plugin-data:// load paths"
                )

            if not parsed.netloc:
                raise RuntimeError(
                    "empty location is not allowed for ruyi-plugin-data:// load paths"
                )

            return resolve_plain_load_path(
                parsed.path,
                plugin_root,
                True,
                plugin_id=parsed.netloc,
            )

        case _:
            raise RuntimeError(
                f"unsupported Ruyi Starlark load path scheme {parsed.scheme}"
            )


def resolve_plain_load_path(
    path: str,
    plugin_root: pathlib.Path,
    is_for_data: bool,
    *,
    originating_file: pathlib.Path | None = None,
    plugin_id: str | None = None,
) -> pathlib.Path:
    if originating_file is None and plugin_id is None:
        raise ValueError("one of originating_file and plugin_id must be specified")

    if plugin_id is None:
        assert originating_file is not None
        rel = originating_file.relative_to(plugin_root)
        plugin_id = rel.parts[0]

    plugin_dir = plugin_root / plugin_id
    if is_for_data:
        plugin_dir = plugin_dir / PLUGIN_DATA_DIR

    p = pathlib.PurePosixPath(path)
    if p.is_absolute():
        return plugin_dir / p.relative_to("/")

    resolved = plugin_dir / p
    if not resolved.is_relative_to(plugin_dir):
        raise ValueError("plain load paths are not allowed to cross plugin boundary")

    return resolved


PLUGIN_ID_RE = re.compile("^[A-Za-z_][A-Za-z0-9_-]*$")


def validate_plugin_id(name: str) -> None:
    if PLUGIN_ID_RE.match(name) is None:
        raise RuntimeError(f"invalid plugin ID '{name}'")
