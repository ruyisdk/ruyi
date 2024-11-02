RUYI = ruyi_plugin_rev(1)


def fn1(mgr):
    def _with_inner(obj):
        return obj * 2
    return RUYI.with_(mgr, _with_inner)


def fn2(mgr):
    def _with_inner(obj):
        return mgr.NoNeXiStEnT
    return RUYI.with_(mgr, _with_inner)


def fn3(mgr, py_fn):
    return RUYI.with_(mgr, py_fn)
