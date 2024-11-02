import pathlib
import sys

from ruyi.ruyipkg import unpack
from ruyi.ruyipkg.unpack_method import UnpackMethod, determine_unpack_method

from ..fixtures import RuyiFileFixtureFactory


def test_unpack_deb(
    ruyi_file: RuyiFileFixtureFactory,
    tmp_path: pathlib.Path,
) -> None:
    with ruyi_file.path("cpp-for-host_14-20240120-6_riscv64.deb") as p:
        assert determine_unpack_method(str(p)) == UnpackMethod.DEB
        unpack.do_unpack(str(p), str(tmp_path), 0, UnpackMethod.DEB, None)
        check = tmp_path / "usr" / "share" / "doc" / "cpp-for-host"
        if sys.version_info >= (3, 12):
            assert check.exists(follow_symlinks=False)
        else:
            # Python 3.11 lacks pathlib.Path.exists(follow_symlinks)
            #
            # we know that this path is going to be a symlink so simply
            # ensuring it's existent is enough; asserting that it is dangling
            # risks breaking CI on systems where the target actually exists
            assert check.lstat() is not None
        assert check.is_symlink()
        assert str(check.readlink()) == "cpp-riscv64-linux-gnu"
