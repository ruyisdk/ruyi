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
    expected_entity_refs = {
        "device:sipeed-lc4a",
        "device:sipeed-lcon4a",
        "device:sipeed-lpi4a",
        "uarch:xiangshan-nanhu",
        "uarch:xuantie-c910",
    }
    assert all(
        f"'{entity_ref}':" in result.stdout for entity_ref in expected_entity_refs
    )
