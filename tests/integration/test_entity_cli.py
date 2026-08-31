import shutil

import pytest

from tests.fixtures import IntegrationTestHarness, RuyiFileFixtureFactory


def test_entity_list_outputs_every_requested_type(
    monkeypatch: pytest.MonkeyPatch,
    ruyi_cli_runner: IntegrationTestHarness,
    ruyi_file: RuyiFileFixtureFactory,
) -> None:
    monkeypatch.setitem(ruyi_cli_runner._env, "RUYI_EXPERIMENTAL", "1")
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        shutil.copytree(
            entities_path,
            ruyi_cli_runner.repo_root / "entities",
            dirs_exist_ok=True,
        )

    result = ruyi_cli_runner(
        "entity",
        "list",
        "--entity-type",
        "device",
        "--entity-type",
        "uarch",
    )

    assert result.exit_code == 0
    assert "'device:sipeed-lpi4a':" in result.stdout
    assert "'uarch:xuantie-c910':" in result.stdout
