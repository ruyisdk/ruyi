from typing import Any, Mapping, Sequence

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.entity_provider import BaseEntityProvider, FSEntityProvider
from ruyi.ruyipkg.entity import EntityStore

from ..fixtures import RuyiFileFixtureFactory


class MockEntityProvider(BaseEntityProvider):
    """A mock entity provider for testing."""

    def discover_schemas(self) -> dict[str, object]:
        """Return a mock schema."""
        return {
            "os": {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "os": {
                        "type": "object",
                        "properties": {
                            "display_name": {"type": "string"},
                            "version": {"type": "string"},
                        },
                        "required": ["display_name"],
                    }
                },
            }
        }

    def load_entities(
        self,
        entity_types: Sequence[str],
    ) -> Mapping[str, Mapping[str, Mapping[str, Any]]]:
        """Return mock entity data if 'os' is in entity_types."""
        if "os" not in entity_types:
            return {}

        return {
            "os": {
                "linux": {"os": {"display_name": "Linux", "version": "6.6.0"}},
                "freebsd": {"os": {"display_name": "FreeBSD", "version": "14.0"}},
            }
        }


def test_entity_store_with_custom_provider(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test using EntityStore with a custom provider."""

    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        # Create store with both filesystem and mock providers
        fs_provider = FSEntityProvider(ruyi_logger, entities_path)
        mock_provider = MockEntityProvider()
        store = EntityStore(ruyi_logger, fs_provider, mock_provider)

        # Verify entity types from both providers are available
        entity_types = set(store.get_entity_types())
        assert "cpu" in entity_types  # from filesystem
        assert "os" in entity_types  # from mock provider

        # Verify we can get entities from both providers
        cpu = store.get_entity("cpu", "xiangshan-nanhu")
        assert cpu is not None
        assert cpu.entity_type == "cpu"

        os = store.get_entity("os", "linux")
        assert os is not None
        assert os.entity_type == "os"
        assert os.display_name == "Linux"
        assert os.data.get("version") == "6.6.0"
