import io
import hashlib

import pytest

from ruyi.ruyipkg.checksum import get_hash_instance, Checksummer


def test_get_hash_instance_supported() -> None:
    # these should not raise any exception
    get_hash_instance("sha256")
    get_hash_instance("sha512")


def test_get_hash_instance_unsupported() -> None:
    with pytest.raises(ValueError, match="checksum algorithm md5 not supported"):
        get_hash_instance("md5")


def test_checksummer_compute() -> None:
    file_content = b"test content"
    expected_sha256 = hashlib.sha256(file_content).hexdigest()
    expected_sha512 = hashlib.sha512(file_content).hexdigest()

    file = io.BytesIO(file_content)
    checksums = {"sha256": expected_sha256, "sha512": expected_sha512}
    checksummer = Checksummer(file, checksums)

    computed_checksums = checksummer.compute()
    assert computed_checksums["sha256"] == expected_sha256


def test_checksummer_check() -> None:
    file_content = b"test content"
    expected_sha256 = hashlib.sha256(file_content).hexdigest()
    expected_sha512 = hashlib.sha512(file_content).hexdigest()

    file = io.BytesIO(file_content)
    checksums = {"sha256": expected_sha256, "sha512": expected_sha512}
    checksummer = Checksummer(file, checksums)

    # This should not raise any exception
    checksummer.check()

    # Modify the file content to cause a checksum mismatch
    file = io.BytesIO(b"modified content")
    checksummer = Checksummer(file, checksums)

    with pytest.raises(ValueError, match="wrong sha256 checksum"):
        checksummer.check()
