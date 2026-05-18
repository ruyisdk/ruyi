import pathlib

from ruyi.ruyipkg.check import (
    check_manifest_file,
    check_repo,
    infer_manifest_repo_context,
    parse_package_selector_args,
)


SHA_STUB = "0" * 64


CANONICAL_MANIFEST = f"""format = "v1"

[metadata]
desc = "Test package"
vendor = {{ name = "Test Vendor", eula = "" }}

[[distfiles]]
name = "src.tar.zst"
size = 0

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[source]
distfiles = ["src.tar.zst"]
"""


NON_CANONICAL_MANIFEST = f"""format = "v1"

[[distfiles]]
size = 0
name = "src.tar.zst"

[distfiles.checksums]
sha256 = "{SHA_STUB}"

[metadata]
vendor = {{ eula = "", name = "Test Vendor" }}
desc = "Test package"

[source]
distfiles = ["src.tar.zst"]
"""


VALID_REPO_CONFIG = """ruyi-repo = "v1"

[[mirrors]]
id = "ruyi-dist"
urls = ["https://example.invalid/dist/"]
"""


def _write_manifest(
    root: pathlib.Path,
    category: str,
    name: str,
    version: str,
    text: str = CANONICAL_MANIFEST,
) -> pathlib.Path:
    manifest_dir = root / "packages" / category / name
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{version}.toml"
    manifest_path.write_text(text, encoding="utf-8")
    return manifest_path


def _write_repo_config(root: pathlib.Path, text: str = VALID_REPO_CONFIG) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.toml").write_text(text, encoding="utf-8")


def test_clean_canonical_manifest_has_no_diagnostics(
    tmp_path: pathlib.Path,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(CANONICAL_MANIFEST, encoding="utf-8")

    assert check_manifest_file(manifest_path) == []


def test_non_canonical_manifest_reports_format_diagnostic(
    tmp_path: pathlib.Path,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(NON_CANONICAL_MANIFEST, encoding="utf-8")

    diagnostics = check_manifest_file(manifest_path)

    assert [diag.code for diag in diagnostics] == ["RYC0001"]
    assert diagnostics[0].hint == f"run: ruyi admin format-manifest {manifest_path}"


def test_malformed_toml_reports_parse_position(tmp_path: pathlib.Path) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text('format = "v1"\n[metadata\n', encoding="utf-8")

    diagnostics = check_manifest_file(manifest_path)

    assert [diag.code for diag in diagnostics] == ["RYC0002"]
    assert diagnostics[0].line == 2
    assert diagnostics[0].column is not None


def test_unknown_manifest_format_reports_invalid_manifest(
    tmp_path: pathlib.Path,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(
        CANONICAL_MANIFEST.replace('format = "v1"', 'format = "v2"'),
        encoding="utf-8",
    )

    diagnostics = check_manifest_file(manifest_path)

    assert [diag.code for diag in diagnostics] == ["RYC0003"]


def test_missing_required_fields_are_reported_without_traceback(
    tmp_path: pathlib.Path,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(
        f"""format = "v1"

[[distfiles]]
name = "src.tar.zst"
size = 0

[distfiles.checksums]
sha256 = "{SHA_STUB}"
""",
        encoding="utf-8",
    )

    diagnostics = check_manifest_file(manifest_path)
    assert [diag.code for diag in diagnostics] == ["RYC0003"]
    assert "metadata" in diagnostics[0].message


def test_accessor_triggered_malformed_data_is_reported(
    tmp_path: pathlib.Path,
) -> None:
    manifest_path = tmp_path / "1.0.0.toml"
    manifest_path.write_text(
        f"""format = "v1"

[metadata]
desc = "Test package"
vendor = {{ name = "Test Vendor", eula = "" }}

[[distfiles]]
size = 0

[distfiles.checksums]
sha256 = "{SHA_STUB}"
""",
        encoding="utf-8",
    )

    diagnostics = check_manifest_file(manifest_path)
    assert [diag.code for diag in diagnostics] == ["RYC0003"]
    assert "name" in diagnostics[0].message


def test_repo_mode_reports_invalid_semver_filenames(
    tmp_path: pathlib.Path,
) -> None:
    _write_repo_config(tmp_path)
    _write_manifest(tmp_path, "source", "sample", "not-semver")

    diagnostics = check_repo(tmp_path)

    assert [diag.code for diag in diagnostics] == ["RYC0004"]


def test_repo_mode_continues_after_bad_files(tmp_path: pathlib.Path) -> None:
    _write_repo_config(tmp_path)
    _write_manifest(tmp_path, "source", "bad-toml", "1.0.0", 'format = "v1"\n[')
    _write_manifest(tmp_path, "source", "bad-version", "not-semver")

    diagnostics = check_repo(tmp_path)

    assert sorted(diag.code for diag in diagnostics) == ["RYC0002", "RYC0004"]


def test_file_mode_infers_repo_context(tmp_path: pathlib.Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        "board-image",
        "example-board",
        "1.2.3",
    )

    context = infer_manifest_repo_context(manifest_path)

    assert context is not None
    assert context.repo_root == tmp_path
    assert context.manifest_root_name == "packages"
    assert context.category == "board-image"
    assert context.name == "example-board"
    assert context.version == "1.2.3"


def test_only_packages_limits_package_diagnostics_but_checks_repo_config(
    tmp_path: pathlib.Path,
) -> None:
    _write_repo_config(tmp_path, 'ruyi-repo = "v1"\n')
    _write_manifest(tmp_path, "source", "ignored", "1.0.0", 'format = "v1"\n[')
    board_manifest = _write_manifest(
        tmp_path,
        "board-image",
        "selected",
        "1.0.0",
        NON_CANONICAL_MANIFEST,
    )
    selector = parse_package_selector_args(["--category-is", "board-image"])

    diagnostics = check_repo(tmp_path, package_selector=selector)

    assert [diag.code for diag in diagnostics] == ["RYC0005", "RYC0001"]
    assert diagnostics[1].path == board_manifest
