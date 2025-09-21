from ruyi.utils import mounts


def test_parse_mounts() -> None:
    sample = r"""
/dev/mapper/foo / btrfs rw,noatime,ssd,discard=async,space_cache=v2,autodefrag,subvolid=5,subvol=/ 0 0
devtmpfs /dev devtmpfs rw,nosuid,size=3896808k,nr_inodes=974202,mode=755,inode64 0 0
tmpfs /dev/shm tmpfs rw,nosuid,nodev,inode64 0 0
tmpfs /tmp/x\040b tmpfs rw,relatime,inode64 0 0
"""

    parsed = mounts.parse_mounts(sample)
    assert len(parsed) == 4

    assert parsed[0].source == "/dev/mapper/foo"
    assert parsed[0].target == "/"
    assert parsed[0].fstype == "btrfs"
    assert parsed[0].options == [
        "rw",
        "noatime",
        "ssd",
        "discard=async",
        "space_cache=v2",
        "autodefrag",
        "subvolid=5",
        "subvol=/",
    ]

    assert parsed[3].source == "tmpfs"
    assert parsed[3].target == "/tmp/x b"
    assert parsed[3].fstype == "tmpfs"
    assert parsed[3].options == ["rw", "relatime", "inode64"]
