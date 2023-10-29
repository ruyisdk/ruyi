import os
import subprocess

from .. import log
from .checksum import Checksummer
from .unpack import do_unpack


class Distfile:
    def __init__(self, url: str, dest: str, size: int, csums: dict[str, str]) -> None:
        self.url = url
        self.dest = dest
        self.size = size
        self.csums = csums

    def ensure(self) -> None:
        log.D(f"checking {self.dest}")
        try:
            st = os.stat(self.dest)
        except FileNotFoundError:
            log.D(f"file {self.dest} not existent")
            return self.fetch()

        if st.st_size < self.size:
            # assume incomplete transmission, try to resume
            log.D(
                f"file {self.dest} appears incomplete: size {st.st_size} < {self.size}; resuming"
            )
            return self.fetch(resume=True)
        elif st.st_size == self.size:
            if self.ensure_integrity_or_rm():
                log.D(f"file {self.dest} passed checks")
                return

            # the file is already gone, re-fetch
            log.D(f"re-fetching {self.url} to {self.dest}")
            return self.fetch()

        log.W(
            f"file {self.dest} is corrupt: size too big ({st.st_size} > {self.size}); deleting"
        )
        os.remove(self.dest)
        return self.fetch()

    def ensure_integrity_or_rm(self) -> bool:
        try:
            with open(self.dest, "rb") as fp:
                cs = Checksummer(fp, self.csums)
                cs.check()
                return True
        except ValueError as e:
            log.W(f"file {self.dest} is corrupt: {e}; deleting")
            os.remove(self.dest)
            return False

    def fetch(self, *, resume: bool = False) -> None:
        # TODO: support more fetchers
        # This list is taken from Gentoo
        argv = ["wget"]
        if resume:
            argv.append("-c")
        argv.extend(("-t", "3", "-T", "60", "--passive-ftp", "-O", self.dest, self.url))

        retcode = subprocess.call(argv)
        if retcode != 0:
            raise RuntimeError(
                f"failed to fetch distfile: command '{' '.join(argv)}' returned {retcode}"
            )

        if not self.ensure_integrity_or_rm():
            raise RuntimeError(
                f"failed to fetch distfile: {self.dest} failed integrity checks"
            )

    def unpack(self, root: str) -> None:
        return do_unpack(self.dest, root)
