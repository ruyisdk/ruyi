from unittest import mock

import platform
import sys

from ruyi.utils.node_info import gather_node_info


def test_gather_node_info_without_freedesktop_os_release():
    """Ensure gather_node_info does not crash when platform.freedesktop_os_release
    is unavailable, e.g. on macOS or other non-systemd/non-freedesktop systems."""
    with mock.patch.object(
        platform,
        "freedesktop_os_release",
        side_effect=OSError("not available"),
    ):
        info = gather_node_info()

    assert info["v"] == 1
    assert info["arch"] == platform.machine()
    assert info["os"] == platform.system().lower()
    assert info["libc_name"] != ""
    assert info["libc_ver"] != ""
    assert info["os_release_id"] != ""
    assert info["os_release_version_id"] != ""
    assert "report_uuid" in info
    assert "ci" in info
    assert "shell" in info


def test_gather_node_info_darwin_like():
    """Ensure gather_node_info produces macOS-compatible fields when running on
    a Darwin-like system without freedesktop_os_release."""
    with (
        mock.patch.object(sys, "platform", "darwin"),
        mock.patch.object(platform, "machine", return_value="arm64"),
        mock.patch.object(platform, "system", return_value="Darwin"),
        mock.patch.object(
            platform,
            "freedesktop_os_release",
            side_effect=OSError("not available"),
        ),
    ):
        info = gather_node_info()

    assert info["os"] == "darwin"
    assert info["arch"] == "arm64"
    assert info["os_release_id"] == "macos"
    assert info["os_release_version_id"] != ""
