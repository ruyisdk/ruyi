import os

from .. import log
from .checksum import Checksummer
from .fetch import BaseFetcher
from .pkg_manifest import DistfileDecl
from .unpack import do_unpack, do_unpack_or_symlink


# https://github.com/ruyisdk/ruyi/issues/46
HELP_ERROR_FETCHING = """
Downloads can fail for a multitude of reasons, most of which should not and
cannot be handled by [yellow]Ruyi[/yellow]. For your convenience though, please check if any
of the following common failure modes apply to you, and take actions
accordingly if one of them turns out to be the case:

* Basic connectivity problems
    - is [yellow]the gateway[/yellow] reachable?
    - is [yellow]common websites[/yellow] reachable?
    - is there any [yellow]DNS pollution[/yellow]?
* Organizational and/or ISP restrictions
    - is there a [yellow]firewall[/yellow] preventing Ruyi traffic?
    - is your [yellow]ISP blocking access[/yellow] to the source website?
* Volatile upstream
    - is the recorded [yellow]link dead[/yellow]? (Please raise a Ruyi issue for a fix!)
"""


class Distfile:
    def __init__(
        self,
        urls: list[str],
        dest: str,
        decl: DistfileDecl,
    ) -> None:
        self.urls = urls
        self.dest = dest
        self.size = decl.size
        self.csums = decl.checksums
        self.strip_components = decl.strip_components
        self.unpack_method = decl.unpack_method

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
            log.D(f"re-fetching {self.dest}")
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
        try:
            return self._fetch_and_ensure_integrity(resume=resume)
        except RuntimeError as e:
            log.F(f"{e}")
            log.stdout(HELP_ERROR_FETCHING)
            raise SystemExit(1)

    def _fetch_and_ensure_integrity(self, *, resume: bool = False) -> None:
        fetcher = BaseFetcher.new(self.urls, self.dest)
        fetcher.fetch(resume=resume)

        if not self.ensure_integrity_or_rm():
            raise RuntimeError(
                f"failed to fetch distfile: {self.dest} failed integrity checks"
            )

    def unpack(self, root: str | None) -> None:
        return do_unpack(self.dest, root, self.strip_components, self.unpack_method)

    def unpack_or_symlink(self, root: str | None) -> None:
        return do_unpack_or_symlink(
            self.dest,
            root,
            self.strip_components,
            self.unpack_method,
        )
