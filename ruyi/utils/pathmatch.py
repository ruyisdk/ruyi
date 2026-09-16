"""A thin wrapper over `pathspec` for .gitignore-style path matching.

Named `pathmatch` (not `pathspec`) to avoid shadowing the third-party
`pathspec` package it wraps.
"""

from __future__ import annotations

from typing import Sequence


class PathMatcher:
    """Matches source-relative POSIX paths against gitignore-style patterns."""

    def __init__(self, patterns: Sequence[str]) -> None:
        import pathspec

        self._spec = pathspec.GitIgnoreSpec.from_lines(patterns)

    def is_excluded(self, path: str) -> bool:
        return self._spec.match_file(path)


def build_matcher(patterns: Sequence[str]) -> PathMatcher:
    return PathMatcher(patterns)
