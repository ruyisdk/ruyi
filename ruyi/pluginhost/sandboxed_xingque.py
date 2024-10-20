import pathlib
from typing import Callable, MutableMapping

import xingque

from . import BasePluginLoader, PluginHostContext
from . import api


class XingquePluginHostContext(
    PluginHostContext[xingque.FrozenModule, xingque.Evaluator]
):
    def make_loader(
        self,
        plugin_root: pathlib.Path,
        originating_file: pathlib.Path,
        module_cache: MutableMapping[str, xingque.FrozenModule],
    ) -> BasePluginLoader[xingque.FrozenModule]:
        return Loader(plugin_root, originating_file, module_cache)

    def make_evaluator(self) -> xingque.Evaluator:
        return xingque.Evaluator()


class Loader(BasePluginLoader[xingque.FrozenModule]):
    """Starlark FileLoader loading from Ruyi repo.

    Load paths take one of the following shapes:

    * relative path: loads the path relative from the originating file's location,
      but crossing plugin boundary is not allowed
    * absolute path: similar to above, but relative to the plugin's Starlark root
    * `ruyi-plugin://${plugin-id}`: loads from the plugin `plugin-id` residing
      in the same repo as the originating plugin, the "entrypoint" being hard-coded
      as `mod.star`
    """

    def do_load_module(
        self,
        resolved_path: pathlib.Path,
        program: str,
        ruyi_host_bridge: Callable[[object], api.RuyiHostAPI],
    ) -> xingque.FrozenModule:
        gb = xingque.GlobalsBuilder.standard()
        gb.set("ruyi_plugin_rev", ruyi_host_bridge)
        globals = gb.build()

        ast = xingque.AstModule.parse(str(resolved_path), program)
        m = xingque.Module()
        ev = xingque.Evaluator(m)
        ev.set_loader(self.make_sub_loader(resolved_path))
        ev.eval_module(ast, globals)
        return m.freeze()
