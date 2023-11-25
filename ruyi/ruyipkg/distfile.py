import os

from .. import log
from .checksum import Checksummer
from .fetch import BaseFetcher
from .pkg_manifest import DistfileDecl
from .unpack import do_unpack


class Distfile:
    def __init__(
        self,
        url: str,
        dest: str,
        decl: DistfileDecl,
    ) -> None:
        self.url = url
        self.dest = dest
        self.size = decl.size
        self.csums = decl.checksums
        self.strip_components = decl.strip_components

    def ensure(self) -> None:
        log.D(f"checking {self.dest}")
        try:
            st = os.stat(self.dest)
        except FileNotFoundError:
            log.D(f"file {self.dest} not existent")
            return self.fetch_and_ensure_integrity()

        if st.st_size < self.size:
            # assume incomplete transmission, try to resume
            log.D(
                f"file {self.dest} appears incomplete: size {st.st_size} < {self.size}; resuming"
            )
            return self.fetch_and_ensure_integrity(resume=True)
        elif st.st_size == self.size:
            if self.ensure_integrity_or_rm():
                log.D(f"file {self.dest} passed checks")
                return

            # the file is already gone, re-fetch
            log.D(f"re-fetching {self.url} to {self.dest}")
            return self.fetch_and_ensure_integrity()

        log.W(
            f"file {self.dest} is corrupt: size too big ({st.st_size} > {self.size}); deleting"
        )
        os.remove(self.dest)
        return self.fetch_and_ensure_integrity()

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

    def fetch_and_ensure_integrity(self, *, resume: bool = False) -> None:
        fetcher = BaseFetcher.new(self.url, self.dest)
        fetcher.fetch(resume=resume)

        if not self.ensure_integrity_or_rm():
            raise RuntimeError(
                f"failed to fetch distfile: {self.dest} failed integrity checks"
            )

    def unpack(self, root: str | None) -> None:
        return do_unpack(self.dest, root, self.strip_components)
