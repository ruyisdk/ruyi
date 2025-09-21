"""Utilities for parsing mount information from /proc/self/mounts."""

import pathlib
import re
from typing import NamedTuple


class MountInfo(NamedTuple):
    source: str
    target: str
    fstype: str
    options: list[str]

    @property
    def source_path(self) -> pathlib.Path:
        return pathlib.Path(self.source)

    @property
    def source_is_blkdev(self) -> bool:
        return self.source_path.is_block_device()


def parse_mounts(contents: str | None = None) -> list[MountInfo]:
    if contents is None:
        try:
            with open("/proc/self/mounts", "r", encoding="utf-8") as f:
                contents = f.read()
        except OSError:
            return []

    mounts: list[MountInfo] = []
    for line in contents.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        source, target, fstype, opts = parts[:4]
        options = opts.split(",")
        source = _unescape_octals(source)
        target = _unescape_octals(target)
        mounts.append(MountInfo(source, target, fstype, options))
    return mounts


def _unescape_octals(s: str) -> str:
    return re.sub(r"\\([0-3][0-7]{2})", lambda m: chr(int(m.group(1), 8)), s)
