import pytest

from ruyi.ruyipkg.entity import EntityStore

from ..fixtures import RuyiFileFixtureFactory


def test_entity_store_discovery(ruyi_file: RuyiFileFixtureFactory) -> None:
    """Test that EntityStore correctly discovers entity types."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(entities_path)
        entity_types = set(store.get_entity_types())

        assert "uarch" in entity_types
        assert "cpu" in entity_types
        assert "device" in entity_types
        assert len(entity_types) == 3


def test_entity_store_get_entity(ruyi_file: RuyiFileFixtureFactory) -> None:
    """Test retrieving entities by type and ID."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(entities_path)

        # Test valid entity retrieval
        cpu = store.get_entity("cpu", "xiangshan-nanhu")
        assert cpu is not None
        assert cpu.entity_type == "cpu"
        assert cpu.id == "xiangshan-nanhu"
        assert cpu.display_name is not None

        # Test non-existent entity
        nonexistent = store.get_entity("cpu", "nonexistent")
        assert nonexistent is None


def test_entity_store_iter_entities(ruyi_file: RuyiFileFixtureFactory) -> None:
    """Test iterating over entities."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(entities_path)

        # Test iterating over a specific type
        cpus = list(store.iter_entities("cpu"))
        assert len(cpus) >= 2  # At least xiangshan-nanhu and xuantie-th1520

        # Test iterating over all entities
        all_entities = list(store.iter_entities(None))
        assert len(all_entities) >= 6  # Total number of entities in the fixture


def test_entity_store_get_entity_by_ref(ruyi_file: RuyiFileFixtureFactory) -> None:
    """Test retrieving entities by reference string."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(entities_path)

        # Test valid reference
        cpu = store.get_entity_by_ref("cpu:xiangshan-nanhu")
        assert cpu is not None
        assert cpu.entity_type == "cpu"
        assert cpu.id == "xiangshan-nanhu"

        # Test invalid reference format
        with pytest.raises(ValueError):
            store.get_entity_by_ref("invalid_reference")


def test_entity_validation(ruyi_file: RuyiFileFixtureFactory) -> None:
    """Test entity validation against schemas."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(entities_path)

        # Force validation by explicitly loading
        store.load_all(validate=True)

        # All entities in the fixture should be valid and loaded successfully
        cpu = store.get_entity("cpu", "xiangshan-nanhu")
        assert cpu is not None

        device = store.get_entity("device", "sipeed-lpi4a")
        assert device is not None
