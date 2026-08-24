from typing import Any

from ruyi.ruyipkg.install import _log_preinstall_notices
from ruyi.ruyipkg.pkg_manifest import BoundPackageManifest, InputPackageManifestType


class _CapturingLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []

    def I(self, s: str = "", *args: Any, **kwargs: Any) -> None:  # noqa: E743
        self.infos.append(s)

    def W(self, s: str = "", *args: Any, **kwargs: Any) -> None:
        self.warnings.append(s)


class _FakeRepo:
    repo_id = "test-repo"
    messages: Any = None


def _make_bound_manifest(vendor: object) -> BoundPackageManifest:
    data: InputPackageManifestType = {
        "format": "v1",
        "metadata": {
            "desc": "test package",
            "vendor": vendor,  # type: ignore[typeddict-item]
        },
        "distfiles": [],
    }
    return BoundPackageManifest(
        "toolchain",
        "gcc",
        "1.0.0",
        data,
        _FakeRepo(),  # type: ignore[arg-type]
    )


def test_certified_notice_emitted_on_install() -> None:
    logger = _CapturingLogger()
    pm = _make_bound_manifest(
        {"name": "Acme", "eula": None, "data": {"ruyisdk": {"certified": True}}}
    )
    _log_preinstall_notices(logger, pm, "en_US.UTF-8")  # type: ignore[arg-type]
    assert any("RuyiSDK Certified" in line for line in logger.infos)


def test_no_certified_notice_when_not_certified() -> None:
    logger = _CapturingLogger()
    pm = _make_bound_manifest({"name": "Acme", "eula": None})
    _log_preinstall_notices(logger, pm, "en_US.UTF-8")  # type: ignore[arg-type]
    assert not any("RuyiSDK Certified" in line for line in logger.infos)
