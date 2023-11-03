import abc
import re
from typing import Literal, Self

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
    def match_in_repo(self, repo: MetadataRepo) -> PackageManifest | None:
        raise NotImplementedError


class NameAtom(Atom):
    def __init__(self, s: str, name: str) -> None:
        super().__init__(s, "name")
        self.name = name

    def match_in_repo(self, repo: MetadataRepo) -> PackageManifest | None:
        # return the latest version of the package named self.name in the given repo
        try:
            return repo.get_pkg_latest_ver(self.name)
        except KeyError:
            return None


class ExprAtom(Atom):
    def __init__(self, s: str, name: str, expr: str) -> None:
        super().__init__(s, "expr")
        self.name = name
        self.exprs = expr.split(",")

    def _is_pm_matching_my_exprs(self, pm: PackageManifest) -> bool:
        for e in self.exprs:
            if not pm.semver.match(e):
                return False
        return True

    def match_in_repo(self, repo: MetadataRepo) -> PackageManifest | None:
        matching_pms = {
            pm.ver: pm
            for pm in repo.iter_pkg_vers(self.name)
            if self._is_pm_matching_my_exprs(pm)
        }
        if not matching_pms:
            return None

        semvers = [pm.semver for pm in matching_pms.values()]
        latest_ver = max(semvers)
        return matching_pms[str(latest_ver)]


class SlugAtom(Atom):
    def __init__(self, s: str) -> None:
        super().__init__(s, "slug")
        self.slug = s[5:]  # strip the "slug:" prefix

    def match_in_repo(self, repo: MetadataRepo) -> PackageManifest | None:
        return repo.get_pkg_by_slug(self.slug)
