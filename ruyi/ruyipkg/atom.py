import abc
import re
from typing import Literal, Self, Tuple

from .pkg_manifest import PackageManifest
from .repo import MetadataRepo


AtomKind = Literal["name"] | Literal["expr"] | Literal["slug"]

RE_ATOM_EXPR = re.compile(r"^([^:(]+)\((.+)\)$")
RE_ATOM_NAME = re.compile(r"^[^:()]+$")


class Atom:
    def __init__(self, s: str, kind: AtomKind) -> None:
        self._s = s
        self._kind: AtomKind = kind

    @property
    def input_str(self) -> str:
        return self._s

    @property
    def kind(self) -> AtomKind:
        return self._kind

    @classmethod
    def parse(cls, s: str) -> Self:
        if s.startswith("slug:"):
            return SlugAtom(s)

        if s.startswith("name:"):
            return NameAtom(s, s[5:])  # strip the "name:" prefix

        if match := RE_ATOM_EXPR.match(s):
            return ExprAtom(s, match[1], match[2])

        # fallback
        if match := RE_ATOM_NAME.match(s):
            return NameAtom(s, s)

        raise ValueError(f"invalid atom: '{s}'")

    @abc.abstractmethod
    def match_in_repo(
        self,
        repo: MetadataRepo,
        include_prerelease_vers: bool,
    ) -> PackageManifest | None:
        raise NotImplementedError


def split_category(name: str) -> Tuple[str | None, str]:
    fragments = name.split("/", 1)
    if len(fragments) == 2:
        return (fragments[0], fragments[1])
    return (None, name)


class NameAtom(Atom):
    def __init__(self, s: str, name: str) -> None:
        super().__init__(s, "name")

        self.category, self.name = split_category(name)

    def match_in_repo(
        self,
        repo: MetadataRepo,
        include_prerelease_vers: bool,
    ) -> PackageManifest | None:
        # return the latest version of the package named self.name in the given repo
        try:
            return repo.get_pkg_latest_ver(
                self.name,
                self.category,
                include_prerelease_vers,
            )
        except KeyError:
            return None


class ExprAtom(Atom):
    def __init__(self, s: str, name: str, expr: str) -> None:
        super().__init__(s, "expr")
        self.exprs = expr.split(",")

        self.category, self.name = split_category(name)

    def _is_pm_matching_my_exprs(self, pm: PackageManifest) -> bool:
        for e in self.exprs:
            if not pm.semver.match(e):
                return False
        return True

    def match_in_repo(
        self,
        repo: MetadataRepo,
        include_prerelease_vers: bool,
    ) -> PackageManifest | None:
        matching_pms = {
            pm.ver: pm
            for pm in repo.iter_pkg_vers(self.name, self.category)
            if self._is_pm_matching_my_exprs(pm)
        }
        if not matching_pms:
            return None

        semvers = [pm.semver for pm in matching_pms.values()]
        if not include_prerelease_vers:
            semvers = [sv for sv in semvers if sv.prerelease is None]
        if not semvers:
            return None
        latest_ver = max(semvers)
        return matching_pms[str(latest_ver)]


class SlugAtom(Atom):
    def __init__(self, s: str) -> None:
        super().__init__(s, "slug")
        self.slug = s[5:]  # strip the "slug:" prefix

    def match_in_repo(
        self,
        repo: MetadataRepo,
        include_prerelease_vers: bool,
    ) -> PackageManifest | None:
        pm = repo.get_pkg_by_slug(self.slug)
        if pm and pm.semver.prerelease:
            return pm if include_prerelease_vers else None
        return pm
