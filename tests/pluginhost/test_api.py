from contextlib import AbstractContextManager
from types import TracebackType

import pytest
import xingque

from ruyi.pluginhost import PluginHostContext

from ..fixtures import RuyiFileFixtureFactory


def test_api_with_(
    ruyi_file: RuyiFileFixtureFactory,
) -> None:
    class MockContextManager(AbstractContextManager[int]):
        def __init__(self) -> None:
            self.entered = 0
            self.exited = 0

        def __enter__(self) -> int:
            self.entered += 1
            return 233

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
        ) -> bool | None:
            self.exited += 1
            return None

    with ruyi_file.plugin_suite("with_") as plugin_root:
        phctx = PluginHostContext(plugin_root)
        ev = xingque.Evaluator()

        fn1 = phctx.get_from_plugin("foo", "fn1")
        assert fn1 is not None
        cm1 = MockContextManager()
        ret1 = ev.eval_function(fn1, cm1)
        assert cm1.entered == 1
        assert cm1.exited == 1
        assert ret1 == 466

        # even when the Starlark side panics, the context manager semantics
        # shall remain enforced
        fn2 = phctx.get_from_plugin("foo", "fn2")
        assert fn2 is not None
        cm2 = MockContextManager()
        with pytest.raises(RuntimeError):
            ev.eval_function(fn2, cm2)
        assert cm2.entered == 1
        assert cm2.exited == 1

        def inner_fn3(x: int) -> int:
            return x - 233

        fn3 = phctx.get_from_plugin("foo", "fn3")
        assert fn3 is not None
        cm3 = MockContextManager()
        ret3 = ev.eval_function(fn3, cm3, inner_fn3)
        assert cm3.entered == 1
        assert cm3.exited == 1
        assert ret3 == 0
