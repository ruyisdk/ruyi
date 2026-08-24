from ruyi.ruyipkg.pkg_manifest import (
    ALL_SERVICE_LEVEL_KINDS,
    InputPackageManifestType,
    PackageManifest,
    PackageServiceLevel,
)

import tomlkit
import pytest


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


def _make_manifest_from_toml(vendor_body: str) -> PackageManifest:
    text = f"""format = "v1"
distfiles = []

[metadata]
desc = "test package"

[metadata.vendor]
name = "Acme"
eula = ""
{vendor_body}"""
    return PackageManifest(tomlkit.loads(text))


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


def test_good_is_a_known_service_level() -> None:
    assert "good" in ALL_SERVICE_LEVEL_KINDS


def test_good_level_reported_as_good() -> None:
    sv = PackageServiceLevel([{"level": "good"}])
    assert sv.level == "good"
    assert sv.has_known_issues is False


def test_known_issue_takes_precedence_over_good() -> None:
    sv = PackageServiceLevel(
        [{"level": "good"}, {"level": "known_issue", "msgid": "x"}]
    )
    assert sv.level == "known_issue"
    assert sv.has_known_issues is True


def test_empty_service_level_defaults_to_untested() -> None:
    sv = PackageServiceLevel([])
    assert sv.level == "untested"


def test_certified_string_false_not_truthy() -> None:
    pm = _make_manifest_from_toml(
        '\n[metadata.vendor.data.ruyisdk]\ncertified = "false"\n'
    )
    assert pm.is_ruyisdk_certified is False


def test_validate_vendor_data_accepts_str_and_bool() -> None:
    pm = _make_manifest_from_toml(
        "\n[metadata.vendor.data.ruyisdk]\ncertified = true\n"
        '\n[metadata.vendor.data.othervendor]\nfoo = "bar"\nflag = false\n'
    )
    pm.validate_vendor_data()  # should not raise


def test_validate_vendor_data_no_data_ok() -> None:
    pm = _make_manifest_from_toml("")
    pm.validate_vendor_data()  # should not raise


def test_validate_vendor_data_rejects_int_value() -> None:
    pm = _make_manifest_from_toml(
        "\n[metadata.vendor.data.othervendor]\ncount = 5\n"
    )
    with pytest.raises(ValueError, match="othervendor"):
        pm.validate_vendor_data()


def test_validate_certified_rejects_non_bool() -> None:
    pm = _make_manifest_from_toml(
        '\n[metadata.vendor.data.ruyisdk]\ncertified = "false"\n'
    )
    with pytest.raises(ValueError, match="certified"):
        pm.validate_vendor_data()
