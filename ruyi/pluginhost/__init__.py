import abc
import pathlib


class PluginHostContext(metaclass=abc.ABCMeta):
    @staticmethod
    def new(plugin_root: pathlib.Path) -> "PluginHostContext":
        return XingquePluginHostContext(plugin_root)

    @abc.abstractmethod
    def load_plugin(self, plugin_id: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def is_plugin_loaded(self, plugin_id: str) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def get_from_plugin(self, plugin_id: str, key: str) -> object | None:
        raise NotImplementedError


from .sandboxed_xingque import XingquePluginHostContext
