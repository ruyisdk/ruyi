import pathlib

import pytest

from ruyi.pluginhost.paths import resolve_ruyi_load_path


@pytest.fixture
def plugin_root(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "plugins"
    (root / "alpha").mkdir(parents=True)
    (root / "alpha" / "mod.star").write_text("")
    (root / "alpha" / "sub.star").write_text("")
    (root / "alpha" / "data").mkdir()
    (root / "alpha" / "data" / "foo.toml").write_text("")
    (root / "beta").mkdir()
    (root / "beta" / "mod.star").write_text("")
    (root / "beta" / "data").mkdir()
    (root / "beta" / "data" / "bar.toml").write_text("")
    return root


def test_plain_relative_within_plugin(plugin_root: pathlib.Path) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    resolved = resolve_ruyi_load_path(
        "sub.star", plugin_root, False, originating, False
    )
    assert resolved == (plugin_root / "alpha" / "sub.star").resolve()


def test_plain_absolute_resolves_against_plugin_root(
    plugin_root: pathlib.Path,
) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    resolved = resolve_ruyi_load_path(
        "/sub.star", plugin_root, False, originating, False
    )
    assert resolved == plugin_root / "alpha" / "sub.star"


def test_plain_cross_plugin_boundary_rejected(plugin_root: pathlib.Path) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(ValueError, match="cross plugin boundary"):
        resolve_ruyi_load_path(
            "../beta/mod.star", plugin_root, False, originating, False
        )


def test_ruyi_plugin_scheme_resolves_entrypoint(plugin_root: pathlib.Path) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    resolved = resolve_ruyi_load_path(
        "ruyi-plugin://beta", plugin_root, False, originating, False
    )
    assert resolved == plugin_root / "beta" / "mod.star"


def test_ruyi_plugin_scheme_rejects_data_context(plugin_root: pathlib.Path) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="ruyi-plugin protocol"):
        resolve_ruyi_load_path(
            "ruyi-plugin://beta", plugin_root, True, originating, False
        )


def test_ruyi_plugin_scheme_rejects_path_segment(
    plugin_root: pathlib.Path,
) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="non-empty path segment"):
        resolve_ruyi_load_path(
            "ruyi-plugin://beta/extra", plugin_root, False, originating, False
        )


def test_ruyi_plugin_scheme_rejects_empty_netloc(
    plugin_root: pathlib.Path,
) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="empty location"):
        resolve_ruyi_load_path("ruyi-plugin://", plugin_root, False, originating, False)


def test_ruyi_plugin_data_scheme_resolves_under_data(
    plugin_root: pathlib.Path,
) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    resolved = resolve_ruyi_load_path(
        "ruyi-plugin-data://beta/bar.toml",
        plugin_root,
        True,
        originating,
        False,
    )
    assert resolved == plugin_root / "beta" / "data" / "bar.toml"


def test_ruyi_plugin_data_scheme_rejects_non_data_context(
    plugin_root: pathlib.Path,
) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="ruyi-plugin-data protocol"):
        resolve_ruyi_load_path(
            "ruyi-plugin-data://beta/bar.toml",
            plugin_root,
            False,
            originating,
            False,
        )


def test_host_scheme_requires_allow_host_fs_access(
    plugin_root: pathlib.Path,
) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="host protocol"):
        resolve_ruyi_load_path(
            "host:///etc/hostname", plugin_root, False, originating, False
        )


def test_host_scheme_returns_absolute_path_when_allowed(
    plugin_root: pathlib.Path,
) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    resolved = resolve_ruyi_load_path(
        "host:///etc/hostname", plugin_root, False, originating, True
    )
    assert resolved == pathlib.Path("/etc/hostname")


def test_fancy_uri_features_rejected(plugin_root: pathlib.Path) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="fancy URI features"):
        resolve_ruyi_load_path(
            "ruyi-plugin://beta?x=1", plugin_root, False, originating, False
        )


def test_unknown_scheme_rejected(plugin_root: pathlib.Path) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="unsupported Ruyi Starlark load path"):
        resolve_ruyi_load_path(
            "gopher://whatever", plugin_root, False, originating, False
        )


def test_double_slash_prefix_rejected(plugin_root: pathlib.Path) -> None:
    originating = plugin_root / "alpha" / "mod.star"
    with pytest.raises(RuntimeError, match="'//' is not allowed"):
        resolve_ruyi_load_path("//evil", plugin_root, False, originating, False)
