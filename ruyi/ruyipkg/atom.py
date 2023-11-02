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
            return ExprAtom(s, match[0], match[1])

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
        self.expr = expr

    def match_in_repo(self, repo: MetadataRepo) -> PackageManifest | None:
        # TODO
        raise NotImplementedError


class SlugAtom(Atom):
    def __init__(self, s: str) -> None:
        super().__init__(s, "slug")
        self.slug = s[5:]  # strip the "slug:" prefix

    def match_in_repo(self, repo: MetadataRepo) -> PackageManifest | None:
        return repo.get_pkg_by_slug(self.slug)
