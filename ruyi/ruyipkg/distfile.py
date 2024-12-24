import os
from typing import Final

from .. import log
from .checksum import Checksummer
from .fetch import BaseFetcher
from .pkg_manifest import DistfileDecl
from .repo import MetadataRepo
from .unpack import do_unpack, do_unpack_or_symlink
from .unpack_method import UnpackMethod


# https://github.com/ruyisdk/ruyi/issues/46
HELP_ERROR_FETCHING: Final = """
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
        mr: MetadataRepo,
    ) -> None:
        self.urls = urls
        self.dest = dest
        self._decl = decl
        self._mr = mr

    @property
    def size(self) -> int:
        return self._decl.size

    @property
    def csums(self) -> dict[str, str]:
        return self._decl.checksums

    @property
    def strip_components(self) -> int:
        return self._decl.strip_components

    @property
    def unpack_method(self) -> UnpackMethod:
        return self._decl.unpack_method

    @property
    def is_fetch_restricted(self) -> bool:
        return self._decl.is_restricted("fetch")

    def render_fetch_instructions(self, lang_code: str) -> str:
        fr = self._decl.fetch_restriction
        if fr is None:
            return ""

        params = {
            "dest_path": self.dest,
        }
        if "params" in fr:
            for k in params.keys():
                # Don't allow package-defined params to override preset params,
                # to reduce surprises for packagers.
                if k in fr["params"]:
                    log.F(
                        f"malformed package fetch instructions: the param named '{k}' is reserved and cannot be overridden by packages"
                    )
                    raise RuntimeError("malformed package fetch instructions")

            params.update(fr["params"])

        return self._mr.messages.render_message(fr["msgid"], lang_code, params)

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
        if self.is_fetch_restricted:
            # the file must be re-fetched if we arrive here, but we cannot,
            # because of the fetch restriction.
            #
            # notify the user and die
            # TODO: allow rendering instructions for all missing fetch-restricted
            # files at once
            log.F(f"the file [yellow]'{self.dest}'[/] cannot be automatically fetched")
            log.I("instructions on fetching this file:")
            log.I(self.render_fetch_instructions(self._mr.global_config.lang_code))
            raise SystemExit(1)

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
