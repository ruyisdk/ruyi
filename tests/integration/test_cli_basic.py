from tests.fixtures import IntegrationTestHarness


def test_cli_version(ruyi_cli_runner: IntegrationTestHarness) -> None:
    for argv in [
        ["--version"],
        ["version"],
    ]:
        result = ruyi_cli_runner(*argv)
        assert result.exit_code == 0
        assert "Ruyi" in result.stdout
        assert "fatal error" not in result.stderr.lower()


def test_cli_list_with_mock_repo(ruyi_cli_runner: IntegrationTestHarness) -> None:
    result = ruyi_cli_runner("list", "--name-contains", "sample-cli")

    assert result.exit_code == 0
    assert "dev-tools/sample-cli" in result.stdout


def test_cli_list_with_custom_package(ruyi_cli_runner: IntegrationTestHarness) -> None:
    sha_stub = "1" * 64
    manifest = (
        'format = "v1"\n'
        'kind = ["source"]\n\n'
        "[metadata]\n"
        'desc = "Custom integration package"\n'
        'vendor = { name = "Integration Tests", eula = "" }\n\n'
        "[[distfiles]]\n"
        'name = "custom-src.tar.zst"\n'
        "size = 0\n\n"
        "[distfiles.checksums]\n"
        f'sha256 = "{sha_stub}"\n'
    )
    ruyi_cli_runner.add_package("examples", "custom-cli", "0.1.0", manifest)

    result = ruyi_cli_runner("list", "--category-is", "examples")

    assert result.exit_code == 0
    assert "examples/custom-cli" in result.stdout
