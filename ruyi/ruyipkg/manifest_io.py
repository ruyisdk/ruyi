import pathlib

from .canonical_dump import dumps_canonical_package_manifest_toml
from .pkg_manifest import PackageManifest


def load_package_manifest_from_path(path: pathlib.Path) -> PackageManifest:
    return PackageManifest.load_from_path(path)


def dump_canonical_package_manifest_from_path(path: pathlib.Path) -> str:
    return dumps_canonical_package_manifest_toml(
        load_package_manifest_from_path(path),
    )
