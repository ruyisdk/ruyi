RUYI = ruyi_plugin_rev(1)


def test_feature():
    return RUYI.has_feature("i18n-v1")


def test_get_locale():
    return RUYI.i18n.locale


def test_messages():
    return {
        "hello-default": RUYI.i18n.msg("hello"),
        "hello-en": RUYI.i18n.msg("hello", "en"),
        "test-format": RUYI.i18n.msg("test-format").format(num=123),
    }
