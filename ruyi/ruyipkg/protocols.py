from typing import Iterable, Protocol

from .pkg_manifest import BoundPackageManifest


class ProvidesPackageManifests(Protocol):
    """A protocol that defines methods for providing package manifests."""

    def get_pkg(
        self,
        name: str,
        category: str,
        ver: str,
    ) -> BoundPackageManifest | None:
        """Returns the package manifest by exact match, or None if not found."""
        ...

    def iter_pkg_manifests(self) -> Iterable[BoundPackageManifest]:
        """Iterates over all package manifests provided by this store."""
        ...

    def iter_pkgs(
        self,
    ) -> Iterable[tuple[str, str, dict[str, BoundPackageManifest]]]:
        """Iterates over all package manifests provided by this store, returning
        ``(category, package_name, pkg_manifests_by_versions)``."""
        ...

    def iter_pkg_vers(
        self,
        name: str,
        category: str | None = None,
    ) -> Iterable[BoundPackageManifest]:
        """Iterates over all versions of a certain package provided by this store,
        specified by name and optionally category."""
        ...

    def get_pkg_latest_ver(
        self,
        name: str,
        category: str | None = None,
        include_prerelease_vers: bool = False,
    ) -> BoundPackageManifest:
        """Returns the latest version of a package provided by this store,
        specified by name and optionally category.

        If ``include_prerelease_vers`` is True, it will also consider prerelease
        versions. Raises KeyError if no such package exists."""
        ...

    # To be removed later along with slug support
    def get_pkg_by_slug(self, slug: str) -> BoundPackageManifest | None:
        """Returns the package with the specified slug from this store, or None
        if not found."""
        ...
