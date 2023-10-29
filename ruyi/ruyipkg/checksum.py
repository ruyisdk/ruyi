import hashlib
from typing import BinaryIO

SUPPORTED_CHECKSUM_KINDS = {"sha256", "sha512"}


def get_hash_instance(kind: str):
    if kind not in SUPPORTED_CHECKSUM_KINDS:
        raise ValueError(f"checksum algorithm {kind} not supported")
    return hashlib.new(kind)


class Checksummer:
    def __init__(self, file: BinaryIO, checksums: dict[str, str]) -> None:
        self.file = file
        self.checksums = checksums

    def check(self, chunksize=4096) -> None:
        checksummers = {kind: get_hash_instance(kind) for kind in self.checksums.keys()}
        while chunk := self.file.read(chunksize):
            for h in checksummers.values():
                h.update(chunk)

        computed_csums = {kind: h.hexdigest() for kind, h in checksummers.items()}
        for kind, expected_csum in self.checksums.items():
            if computed_csums[kind] != expected_csum:
                raise ValueError(
                    f"wrong {kind} checksum: want {expected_csum}, got {computed_csums[kind]}"
                )
