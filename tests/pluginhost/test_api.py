from contextlib import AbstractContextManager
from types import TracebackType
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import pytest

from ruyi.log import RuyiLogger
from ruyi.pluginhost.ctx import PluginHostContext
from ruyi.ruyipkg.msg import RepoMessageStore

from ..fixtures import RuyiFileFixtureFactory


def test_api_has_feature(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    with ruyi_file.plugin_suite("api_tests") as plugin_root:
        phctx = PluginHostContext.new(ruyi_logger, plugin_root)
        ev = phctx.make_evaluator()

        nonexistent = phctx.get_from_plugin("has_feature", "check_nonexistent_feature")
        assert nonexistent is not None
        assert not ev.eval_function(nonexistent)


def test_api_feature_i18n_v1_dynamic_exposure(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    with ruyi_file.plugin_suite("api_tests") as plugin_root:
        phctx1 = PluginHostContext.new(
            ruyi_logger,
            plugin_root,
            # no locale or message store factory
        )
        ev1 = phctx1.make_evaluator()
        feature1 = phctx1.get_from_plugin("i18n-v1", "test_feature")
        assert not ev1.eval_function(feature1)

        phctx2 = PluginHostContext.new(
            ruyi_logger,
            plugin_root,
            locale="en_US",
            # no message store factory
        )
        ev2 = phctx2.make_evaluator()
        feature2 = phctx2.get_from_plugin("i18n-v1", "test_feature")
        assert not ev2.eval_function(feature2)

        with open(plugin_root / "test-messages.toml", "rb") as f:
            msgs = tomllib.load(f)
        phctx3 = PluginHostContext.new(
            ruyi_logger,
            plugin_root,
            # no locale
            message_store_factory=lambda: RepoMessageStore.from_object(msgs),
        )
        ev3 = phctx3.make_evaluator()
        feature3 = phctx3.get_from_plugin("i18n-v1", "test_feature")
        assert ev3.eval_function(feature3)


def test_api_feature_i18n_v1(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    with ruyi_file.plugin_suite("api_tests") as plugin_root:
        with open(plugin_root / "test-messages.toml", "rb") as f:
            msgs = tomllib.load(f)
        rm = RepoMessageStore.from_object(msgs)

        phctx = PluginHostContext.new(
            ruyi_logger,
            plugin_root,
            locale="zh_CN",
            message_store_factory=lambda: rm,
        )
        ev = phctx.make_evaluator()

        test_feature = phctx.get_from_plugin("i18n-v1", "test_feature")
        assert test_feature is not None
        assert ev.eval_function(test_feature)

        get_locale = phctx.get_from_plugin("i18n-v1", "test_get_locale")
        assert get_locale is not None
        locale = ev.eval_function(get_locale)
        assert locale == "zh_CN"

        test_messages = phctx.get_from_plugin("i18n-v1", "test_messages")
        assert test_messages is not None
        msgs_result = ev.eval_function(test_messages)
        assert msgs_result == {
            "hello-default": "你好世界！",
            "hello-en": "Hello world!",
            "test-format": "123 条消息",
        }


def test_api_with_(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
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

    with ruyi_file.plugin_suite("api_tests") as plugin_root:
        phctx = PluginHostContext.new(ruyi_logger, plugin_root)
        ev = phctx.make_evaluator()

        fn1 = phctx.get_from_plugin("with_", "fn1")
        assert fn1 is not None
        cm1 = MockContextManager()
        ret1 = ev.eval_function(fn1, cm1)
        assert cm1.entered == 1
        assert cm1.exited == 1
        assert ret1 == 466

        # even when the plugin side panics, the context manager semantics
        # shall remain enforced
        fn2 = phctx.get_from_plugin("with_", "fn2")
        assert fn2 is not None
        cm2 = MockContextManager()
        with pytest.raises((RuntimeError, AttributeError)):
            ev.eval_function(fn2, cm2)
        assert cm2.entered == 1
        assert cm2.exited == 1

        def inner_fn3(x: int) -> int:
            return x - 233

        fn3 = phctx.get_from_plugin("with_", "fn3")
        assert fn3 is not None
        cm3 = MockContextManager()
        ret3 = ev.eval_function(fn3, cm3, inner_fn3)
        assert cm3.entered == 1
        assert cm3.exited == 1
        assert ret3 == 0
