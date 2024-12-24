import pathlib
import re
from typing import Final
from urllib.parse import unquote, urlparse

PLUGIN_ENTRYPOINT_FILENAME: Final = "mod.star"
PLUGIN_DATA_DIR: Final = "data"
PLUGIN_ID_RE: Final = re.compile("^[A-Za-z_][A-Za-z0-9_-]*$")


def validate_plugin_id(name: str) -> None:
    if PLUGIN_ID_RE.match(name) is None:
        raise RuntimeError(f"invalid plugin ID '{name}'")


def get_plugin_dir(plugin_id: str, plugin_root: pathlib.Path) -> pathlib.Path:
    validate_plugin_id(plugin_id)
    return plugin_root / plugin_id


def resolve_ruyi_load_path(
    path: str,
    plugin_root: pathlib.Path,
    is_for_data: bool,
    originating_file: pathlib.Path,
    allow_host_fs_access: bool,
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

        case "host":
            if not allow_host_fs_access:
                raise RuntimeError("the host protocol is not allowed in this context")

            if not parsed.path:
                raise RuntimeError(
                    "empty path segment is not allowed for host:// load paths"
                )

            if parsed.netloc:
                raise RuntimeError(
                    "non-empty location is not allowed for host:// load paths"
                )

            return pathlib.Path(parsed.path)

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
        raise ValueError("one of originating_file or plugin_id must be specified")

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

    resolved = (plugin_dir / p).resolve()
    if not resolved.is_relative_to(plugin_dir):
        raise ValueError("plain load paths are not allowed to cross plugin boundary")

    return resolved
