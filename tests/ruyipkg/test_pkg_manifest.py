from ruyi.ruyipkg.pkg_manifest import InputPackageManifestType, PackageManifest


def _make_manifest(vendor: object) -> PackageManifest:
    data: InputPackageManifestType = {
        "format": "v1",
        "metadata": {
            "desc": "test package",
            "vendor": vendor,  # type: ignore[typeddict-item]
        },
        "distfiles": [],
    }
    return PackageManifest(data)


def test_ruyisdk_certified_true() -> None:
    pm = _make_manifest(
        {"name": "Acme", "eula": None, "data": {"ruyisdk": {"certified": True}}}
    )
    assert pm.is_ruyisdk_certified is True


def test_ruyisdk_certified_false_when_flag_false() -> None:
    pm = _make_manifest(
        {"name": "Acme", "eula": None, "data": {"ruyisdk": {"certified": False}}}
    )
    assert pm.is_ruyisdk_certified is False


def test_ruyisdk_certified_false_when_block_absent() -> None:
    pm = _make_manifest({"name": "Acme", "eula": None})
    assert pm.is_ruyisdk_certified is False


def test_ruyisdk_certified_false_when_data_present_without_ruyisdk() -> None:
    pm = _make_manifest(
        {"name": "Acme", "eula": None, "data": {"othervendor": {"foo": "bar"}}}
    )
    assert pm.is_ruyisdk_certified is False


def test_vendor_data_returns_generic_block() -> None:
    pm = _make_manifest(
        {"name": "Acme", "eula": None, "data": {"othervendor": {"foo": "bar"}}}
    )
    assert pm.vendor_data("othervendor") == {"foo": "bar"}


def test_vendor_data_returns_none_when_absent() -> None:
    pm = _make_manifest({"name": "Acme", "eula": None})
    assert pm.vendor_data("othervendor") is None
