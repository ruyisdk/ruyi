import tomlkit

from ruyi.ruyipkg.canonical_dump import dumps_canonical_package_manifest_toml
from ruyi.ruyipkg.pkg_manifest import PackageManifest

from ..fixtures import RuyiFileFixtureFactory


def test_format_manifest(ruyi_file: RuyiFileFixtureFactory) -> None:
    with ruyi_file.path("ruyipkg_suites", "format_manifest") as fixtures_dir:
        # Find pairs of before/after files
        files = list(fixtures_dir.glob("*.toml"))
        cases = [f.name[:-12] for f in files if f.name.endswith(".before.toml")]

        for case_name in cases:
            # Determine the expected output file name
            before_file = fixtures_dir / f"{case_name}.before.toml"
            after_file = fixtures_dir / f"{case_name}.after.toml"
            assert after_file.exists(), f"Expected file {after_file} does not exist"

            with open(before_file, "rb") as f:
                data = PackageManifest(tomlkit.load(f))

            # Process with the formatter
            result = dumps_canonical_package_manifest_toml(data)

            # Read the expected output
            with open(after_file, "r", encoding="utf-8") as g:
                expected = g.read()

            assert result == expected, (
                f"Formatted output for {before_file.name} doesn't match expected output. "
                f"Check {after_file.name} for the expected formatting result."
            )
