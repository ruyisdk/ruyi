import hashlib
from typing import BinaryIO, Final, Iterable

SUPPORTED_CHECKSUM_KINDS: Final = {"sha256", "sha512"}


def get_hash_instance(kind: str) -> "hashlib._Hash":
    if kind not in SUPPORTED_CHECKSUM_KINDS:
        raise ValueError(f"checksum algorithm {kind} not supported")
    return hashlib.new(kind)


class Checksummer:
    def __init__(self, file: BinaryIO, checksums: dict[str, str]) -> None:
        self.file = file
        self.checksums = checksums

    def check(self) -> None:
        computed_csums = self.compute()
        for kind, expected_csum in self.checksums.items():
            if computed_csums[kind] != expected_csum:
                raise ValueError(
                    f"wrong {kind} checksum: want {expected_csum}, got {computed_csums[kind]}"
                )

    def compute(
        self,
        kinds: Iterable[str] | None = None,
        chunksize: int = 4096,
    ) -> dict[str, str]:
        if kinds is None:
            kinds = self.checksums.keys()

        checksummers = {kind: get_hash_instance(kind) for kind in kinds}
        while chunk := self.file.read(chunksize):
            for h in checksummers.values():
                h.update(chunk)

        return {kind: h.hexdigest() for kind, h in checksummers.items()}
