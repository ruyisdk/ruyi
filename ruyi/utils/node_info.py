import glob
import os
import pathlib
import platform
import re
import subprocess
import sys
from typing import Final, Mapping, TypedDict, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from typing_extensions import NotRequired

from .ci import probe_for_ci


class NodeInfo(TypedDict):
    v: int
    report_uuid: str

    arch: str
    ci: str
    libc_name: str
    libc_ver: str
    os: str
    os_release_id: str
    os_release_version_id: str
    shell: str

    riscv_machine: "NotRequired[RISCVMachineInfo]"


class RISCVMachineInfo(TypedDict):
    model_name: str
    cpu_count: int
    isa: str
    uarch: str
    uarch_csr: str
    mmu: str


def probe_for_libc() -> tuple[str, str]:
    r = platform.libc_ver()
    if r[0] and r[1]:
        return r

    # check for musl ld.so at the upstream standard paths, because
    # platform.libc_ver() as of Python 3.12 does not know how to handle musl
    #
    # see https://wiki.musl-libc.org/guidelines-for-distributions
    musl_lds = glob.glob("/lib/ld-musl-*.so.1")
    if musl_lds:
        # run it and check for "Version *.*.*"
        # in case of multiple hits (hybrid-architecture sysroot?), hope the
        # first one that successfully returns something is the native one
        for p in musl_lds:
            if ver := _try_get_musl_ver(p):
                return ("musl", ver)

    return ("unknown", "unknown")


_MUSL_VERSION_RE: Final = re.compile(rb"(?m)^Version ([0-9.]+)$")


def _try_get_musl_ver(ldso_path: str) -> str | None:
    res = subprocess.run([ldso_path], stderr=subprocess.PIPE)
    if m := _MUSL_VERSION_RE.search(res.stderr):
        return m.group(1).decode("ascii", "ignore")
    return None


def _try_parse_hex(v: str) -> int | None:
    if not v.startswith("0x"):
        return None
    try:
        return int(v[2:], 16)
    except ValueError:
        return None


def probe_for_riscv_machine_info(
    model_name: str | None = None,
    cpuinfo_data: str | None = None,
) -> RISCVMachineInfo | None:
    if model_name is None:
        try:
            with open(
                "/sys/firmware/devicetree/base/model",
                "r",
                encoding="utf-8",
            ) as fp:
                model_name = fp.read().strip(" \n\t\x00")
        except Exception:
            pass

        if not model_name:
            model_name = "unknown"

    if cpuinfo_data is None:
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8") as fp:
                cpuinfo_data = fp.read()
        except Exception:
            pass

    cpu_count = 0
    isa, mmu, uarch = "unknown", "unknown", "unknown"
    mvendorid: int | None = None
    marchid: int | None = None
    mimpid: int | None = None
    if cpuinfo_data is not None:
        for line in cpuinfo_data.split("\n"):
            if not line:
                continue

            try:
                k, v = line.split(": ", 1)
            except ValueError:
                # malformed line: non-empty but no ": "
                continue

            k = k.strip(" \t")
            v = v.strip()

            match k:
                case "processor":
                    cpu_count += 1
                case "isa":
                    isa = v
                case "mmu":
                    mmu = v
                case "uarch":
                    uarch = v
                case "mvendorid":
                    mvendorid = _try_parse_hex(v)
                case "marchid":
                    marchid = _try_parse_hex(v)
                case "mimpid":
                    mimpid = _try_parse_hex(v)
                case _:
                    continue

    if mvendorid is not None and marchid is not None and mimpid is not None:
        uarch_csr = f"{mvendorid:x}:{marchid:x}:{mimpid:x}"
    else:
        uarch_csr = "unknown"

    return {
        "model_name": model_name,
        "cpu_count": cpu_count,
        "isa": isa,
        "mmu": mmu,
        "uarch": uarch,
        "uarch_csr": uarch_csr,
    }


def probe_for_shell(os_environ: Mapping[str, str]) -> str:
    if x := os_environ.get("SHELL"):
        return os.path.basename(x)
    return "unknown"


def probe_for_container_runtime(os_environ: Mapping[str, str]) -> str:
    """Check if we are likely running in a container. Probes FS and environment
    for signatures of known container runtimes."""

    # check environment markers first

    if "KUBERNETES_SERVICE_HOST" in os_environ:
        return "kubernetes"

    if "container" in os_environ:
        v = os_environ["container"].lower()
        if v == "oci":
            return "other-oci-compliant"
        # could be e.g. "lxc", "lxc-libvirt", "systemd-nspawn", etc.
        return v

    # check for filesystem markers

    if os.path.exists("/run/.containerenv"):
        return "podman"
    # Docker must be checked after Podman
    if os.path.exists("/.dockerenv"):
        return "docker"

    try:
        v = pathlib.Path("/run/systemd/container").read_text(encoding="utf-8").strip()
        if v:
            return v.lower()
    except Exception:
        pass

    if _probe_for_wsl():
        return "wsl"

    return "unknown"


def _probe_for_wsl() -> bool:
    if sys.platform != "linux":
        return False
    # http://github.com/Microsoft/WSL/issues/423#issuecomment-221627364
    for path in ("/proc/sys/kernel/osrelease", "/proc/version"):
        try:
            ver = pathlib.Path(path).read_text(encoding="utf-8")
        except Exception:
            continue
        return "Microsoft" in ver or "WSL" in ver
    return False


def gather_node_info(report_uuid: uuid.UUID | None = None) -> NodeInfo:
    arch = platform.machine()
    libc = probe_for_libc()
    os_release = platform.freedesktop_os_release()

    os_version = os_release.get("VERSION_CODENAME")  # works on e.g. Debian
    if not os_version:
        os_version = os_release.get("VERSION_ID")  # works on e.g. openEuler, Gentoo
    if not os_version:
        os_version = "unknown"

    data: NodeInfo = {
        "v": 1,
        "report_uuid": report_uuid.hex if report_uuid is not None else uuid.uuid4().hex,
        "arch": arch,
        "ci": probe_for_ci(os.environ) or "maybe-not",
        "libc_name": libc[0],
        "libc_ver": libc[1],
        "os": sys.platform,
        "os_release_id": os_release.get("ID", "unknown"),
        "os_release_version_id": os_version,
        "shell": probe_for_shell(os.environ),
    }

    if arch.startswith("riscv"):
        if riscv_machine := probe_for_riscv_machine_info():
            data["riscv_machine"] = riscv_machine

    return data
