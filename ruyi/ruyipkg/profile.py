from os import PathLike
from typing import Any, Iterable, TypeGuard, cast

from ..pluginhost.ctx import PluginHostContext, SupportsEvalFunction
from .pkg_manifest import EmulatorFlavor


class InvalidProfilePluginError(RuntimeError):
    def __init__(self, s: str) -> None:
        super().__init__(f"invalid arch profile plugin: {s}")


def validate_list_str(x: object) -> TypeGuard[list[str]]:
    if not isinstance(x, list):
        return False
    x = cast(list[object], x)
    return all(isinstance(y, str) for y in x)


def validate_list_str_or_none(x: object) -> TypeGuard[list[str] | None]:
    return True if x is None else validate_list_str(x)


def validate_dict_str_str(x: object) -> TypeGuard[dict[str, str]]:
    if not isinstance(x, dict):
        return False
    for k, v in cast(dict[object, object], x).items():
        if not isinstance(k, str) or not isinstance(v, str):
            return False
    return True


class PluginProfileProvider:
    def __init__(
        self,
        phctx: PluginHostContext[Any, SupportsEvalFunction],
        plugin_id: str,
    ) -> None:
        self._phctx = phctx
        self._plugin_id = plugin_id
        self._ev = phctx.make_evaluator()

    def _must_get(self, name: str) -> object:
        if v := self._phctx.get_from_plugin(self._plugin_id, name):
            return v
        raise InvalidProfilePluginError(
            f"'{name}' not found in plugin '{self._plugin_id}'"
        )

    def list_all_profile_ids(self) -> list[str]:
        fn = self._must_get("list_all_profile_ids_v1")
        ret = self._ev.eval_function(fn)
        if not validate_list_str(ret):
            raise InvalidProfilePluginError(
                "list_all_profile_ids must return list[str]"
            )

        return ret

    def list_needed_quirks(self, profile_id: str) -> list[str] | None:
        # For backward compatibility, try "list_needed_quirks_v1" first, then
        # fall back to "list_needed_flavors_v1" if the former is not available.
        fn = self._phctx.get_from_plugin(self._plugin_id, "list_needed_quirks_v1")
        if fn is None:
            fn = self._must_get("list_needed_flavors_v1")

        ret = self._ev.eval_function(fn, profile_id)
        if not validate_list_str_or_none(ret):
            raise InvalidProfilePluginError(
                "list_needed_quirks_v1 must return list[str] | None"
            )

        return ret

    def get_common_flags(self, profile_id: str, toolchain_quirks: list[str]) -> str:
        result = self._maybe_get_common_flags_v2(profile_id, toolchain_quirks)
        if result is not None:
            return result
        return self._get_common_flags_v1(profile_id)

    def _get_common_flags_v1(self, profile_id: str) -> str:
        fn = self._must_get("get_common_flags_v1")
        ret = self._ev.eval_function(fn, profile_id)
        if not isinstance(ret, str):
            raise InvalidProfilePluginError("get_common_flags_v1 must return str")

        return ret

    def _maybe_get_common_flags_v2(
        self,
        profile_id: str,
        toolchain_flavors: list[str],
    ) -> str | None:
        fn = self._phctx.get_from_plugin(self._plugin_id, "get_common_flags_v2")
        if fn is None:
            return None

        ret = self._ev.eval_function(fn, profile_id, toolchain_flavors)
        if not isinstance(ret, str):
            raise InvalidProfilePluginError("get_common_flags_v2 must return str")

        return ret

    def get_needed_emulator_pkg_flavors(
        self,
        profile_id: str,
        flavor: EmulatorFlavor,
    ) -> Iterable[str]:
        fn = self._must_get("get_needed_emulator_pkg_flavors_v1")
        ret = self._ev.eval_function(
            fn,
            profile_id,
            flavor,
        )
        if not validate_list_str(ret):
            raise InvalidProfilePluginError(
                "get_needed_emulator_pkg_flavors_v1 must return list[str]"
            )

        return ret

    def check_emulator_flavor(
        self,
        profile_id: str,
        flavor: EmulatorFlavor,
        emulator_pkg_flavors: list[str] | None,
    ) -> bool:
        fn = self._must_get("check_emulator_flavor_v1")
        ret = self._ev.eval_function(
            fn,
            profile_id,
            flavor,
            emulator_pkg_flavors,
        )
        if not isinstance(ret, bool):
            raise InvalidProfilePluginError("check_emulator_flavor_v1 must return bool")

        return ret

    def get_env_config_for_emu_flavor(
        self,
        profile_id: str,
        flavor: EmulatorFlavor,
        sysroot: PathLike[Any] | None,
    ) -> dict[str, str] | None:
        fn = self._must_get("get_env_config_for_emu_flavor_v1")
        ret = self._ev.eval_function(
            fn,
            profile_id,
            flavor,
            str(sysroot) if sysroot is not None else None,
        )
        if not validate_dict_str_str(ret):
            raise InvalidProfilePluginError(
                "get_env_config_for_emu_flavor_v1 must return dict[str, str]"
            )

        return ret


class ProfileProxy:
    def __init__(
        self,
        provider: PluginProfileProvider,
        arch: str,
        profile_id: str,
    ) -> None:
        self._provider = provider
        self._arch = arch
        self._id = profile_id

    @property
    def arch(self) -> str:
        return self._arch

    @property
    def id(self) -> str:
        return self._id

    @property
    def need_quirks(self) -> set[str]:
        r = self._provider.list_needed_quirks(self._id)
        return set(r) if r else set()

    def get_common_flags(self, toolchain_flavors: list[str]) -> str:
        return self._provider.get_common_flags(self._id, toolchain_flavors)

    def get_needed_emulator_pkg_flavors(
        self,
        flavor: EmulatorFlavor,
    ) -> set[str]:
        return set(self._provider.get_needed_emulator_pkg_flavors(self._id, flavor))

    def check_emulator_flavor(
        self,
        flavor: EmulatorFlavor,
        emulator_pkg_flavors: list[str] | None,
    ) -> bool:
        return self._provider.check_emulator_flavor(
            self._id, flavor, emulator_pkg_flavors
        )

    def get_env_config_for_emu_flavor(
        self,
        flavor: EmulatorFlavor,
        sysroot: PathLike[Any] | None,
    ) -> dict[str, str] | None:
        return self._provider.get_env_config_for_emu_flavor(self._id, flavor, sysroot)
