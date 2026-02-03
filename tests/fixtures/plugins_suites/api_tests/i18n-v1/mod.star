RUYI = ruyi_plugin_rev(1)


def test_feature():
    return RUYI.has_feature("i18n-v1")


def test_get_locale():
    return RUYI.locale
