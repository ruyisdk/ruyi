from ruyi.ruyipkg import host


def test_canonicalize_arch() -> None:
    testcases = [
        ("AMD64", "x86_64"),
        ("amd64", "x86_64"),
        ("EM64T", "x86_64"),
        ("ARM64", "aarch64"),
        ("arm64", "aarch64"),
        ("x86_64", "x86_64"),
        ("aarch64", "aarch64"),
        ("riscv64", "riscv64"),
    ]

    for input, expected in testcases:
        assert host.canonicalize_arch_str(input) == expected


def test_canonicalize_host() -> None:
    assert host.canonicalize_host_str("arm64") == "linux/aarch64"
    assert host.canonicalize_host_str("aarch64") == "linux/aarch64"
    assert host.canonicalize_host_str("darwin/arm64") == "darwin/aarch64"
    assert host.canonicalize_host_str("linux/riscv64") == "linux/riscv64"
    assert host.canonicalize_host_str("riscv64") == "linux/riscv64"
    assert host.canonicalize_host_str("win32/AMD64") == "windows/x86_64"
    assert host.canonicalize_host_str("win32/ARM64") == "windows/aarch64"
    assert host.canonicalize_host_str("x86_64") == "linux/x86_64"

    assert (
        host.canonicalize_host_str(host.RuyiHost("win32", "AMD64")) == "windows/x86_64"
    )
