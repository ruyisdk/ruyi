import pytest

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.entity import EntityStore
from ruyi.ruyipkg.entity_provider import FSEntityProvider

from ..fixtures import RuyiFileFixtureFactory


def test_entity_store_discovery(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test that EntityStore correctly discovers entity types."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))
        entity_types = set(store.get_entity_types())

        assert "arch" in entity_types
        assert "cpu" in entity_types
        assert "device" in entity_types
        assert "uarch" in entity_types
        assert len(entity_types) == 4


def test_entity_store_get_entity(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test retrieving entities by type and ID."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Test valid entity retrieval
        cpu = store.get_entity("cpu", "xiangshan-nanhu")
        assert cpu is not None
        assert cpu.entity_type == "cpu"
        assert cpu.id == "xiangshan-nanhu"
        assert cpu.display_name is not None

        # Test non-existent entity
        nonexistent = store.get_entity("cpu", "nonexistent")
        assert nonexistent is None


def test_entity_store_iter_entities(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test iterating over entities."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Test iterating over a specific type
        cpus = list(store.iter_entities("cpu"))
        assert len(cpus) >= 2  # At least xiangshan-nanhu and xuantie-th1520

        # Test iterating over all entities
        all_entities = list(store.iter_entities(None))
        assert len(all_entities) >= 6  # Total number of entities in the fixture


def test_entity_store_get_entity_by_ref(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test retrieving entities by reference string."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Test valid reference
        cpu = store.get_entity_by_ref("cpu:xiangshan-nanhu")
        assert cpu is not None
        assert cpu.entity_type == "cpu"
        assert cpu.id == "xiangshan-nanhu"

        # Test invalid reference format
        with pytest.raises(ValueError):
            store.get_entity_by_ref("invalid_reference")


def test_entity_validation(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test entity validation against schemas."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Force validation by explicitly loading
        store.load_all(validate=True)

        # All entities in the fixture should be valid and loaded successfully
        cpu = store.get_entity("cpu", "xiangshan-nanhu")
        assert cpu is not None

        device = store.get_entity("device", "sipeed-lpi4a")
        assert device is not None


def test_entity_related_refs(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test retrieving related entity references from an entity."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Test entity with related entities
        cpu = store.get_entity("cpu", "xiangshan-nanhu")
        assert cpu is not None
        assert isinstance(cpu.related_refs, list)
        assert "uarch:xiangshan-nanhu" in cpu.related_refs

        # Test device with related entities
        device = store.get_entity("device", "sipeed-lpi4a")
        assert device is not None
        assert isinstance(device.related_refs, list)
        assert "cpu:xuantie-th1520" in device.related_refs


def test_get_related_entities(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test retrieving related entities from an entity."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Test CPU entity with a related uarch entity
        cpu = store.get_entity("cpu", "xiangshan-nanhu")
        assert cpu is not None

        related_entities = store.list_related_entities(cpu)
        assert len(related_entities) == 1
        assert related_entities[0].entity_type == "uarch"
        assert related_entities[0].id == "xiangshan-nanhu"

        # Test device entity with a related CPU entity
        device = store.get_entity("device", "sipeed-lpi4a")
        assert device is not None

        related_entities = store.list_related_entities(device)
        assert len(related_entities) == 1
        assert related_entities[0].entity_type == "cpu"
        assert related_entities[0].id == "xuantie-th1520"


def test_traverse_related_entities_direct(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test traversing directly related entities."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Start from a device entity
        device = store.get_entity("device", "sipeed-lpi4a")
        assert device is not None

        # Get direct related entities (transitive=False)
        related = list(store.traverse_related_entities(device, transitive=False))

        # Should only include the directly related CPU entity
        assert len(related) == 1
        assert related[0].entity_type == "cpu"
        assert related[0].id == "xuantie-th1520"


def test_traverse_related_entities_transitive(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test traversing the transitive closure of related entities."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Start from a device entity
        device = store.get_entity("device", "sipeed-lpi4a")
        assert device is not None

        # Get transitive related entities (transitive=True)
        related = list(store.traverse_related_entities(device, transitive=True))

        # Should include:
        # 1. The directly related CPU entity
        # 2. Any entities related to that CPU entity
        assert len(related) >= 1

        # Check that the CPU is included
        cpu_entities = [e for e in related if e.entity_type == "cpu"]
        assert len(cpu_entities) >= 1
        assert any(e.id == "xuantie-th1520" for e in cpu_entities)

        # If the CPU has related entities, they should also be included
        # Get the CPU entity to check its relationships
        cpu = store.get_entity("cpu", "xuantie-th1520")
        if cpu and cpu.related_refs:
            for ref in cpu.related_refs:
                entity_type, entity_id = ref.split(":", 1)
                assert any(
                    e.entity_type == entity_type and e.id == entity_id for e in related
                )


def test_traverse_related_entities_with_type_filter(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test traversing related entities with filtering by entity type."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        # Start from a device entity reference
        ref = "device:sipeed-lpi4a"

        # Only get entities of type "cpu"
        cpu_entities = list(
            store.traverse_related_entities(
                ref,
                transitive=True,
                entity_types=["cpu"],
            )
        )

        # Should only include CPU entities
        assert all(e.entity_type == "cpu" for e in cpu_entities)
        assert any(e.id == "xuantie-th1520" for e in cpu_entities)

        # Only get entities of type "uarch"
        uarch_entities = list(
            store.traverse_related_entities(
                ref,
                transitive=True,
                entity_types=["uarch"],
            )
        )

        # Should only include uarch entities
        assert all(e.entity_type == "uarch" for e in uarch_entities)

        # Test with multiple entity types
        mixed_entities = list(
            store.traverse_related_entities(
                ref,
                transitive=True,
                entity_types=["cpu", "uarch"],
            )
        )

        # Should only include entities of the specified types
        assert all(e.entity_type in ["cpu", "uarch"] for e in mixed_entities)
        assert not any(e.entity_type == "device" for e in mixed_entities)


def test_entity_store_is_entity_related_to(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
) -> None:
    """Test the ``is_related_to`` method of ``EntityStore``."""
    with ruyi_file.path("ruyipkg_suites", "entities_v0_smoke") as entities_path:
        store = EntityStore(ruyi_logger, FSEntityProvider(ruyi_logger, entities_path))

        assert store.is_entity_related_to(
            "cpu:xiangshan-nanhu",
            "uarch:xiangshan-nanhu",
        )
        assert store.is_entity_related_to(
            "uarch:xiangshan-nanhu",
            "cpu:xiangshan-nanhu",
        )
        assert not store.is_entity_related_to(
            "cpu:xiangshan-nanhu",
            "uarch:xuantie-c910",
        )
        assert not store.is_entity_related_to(
            "uarch:xuantie-c910",
            "cpu:xiangshan-nanhu",
        )
        assert not store.is_entity_related_to(
            "cpu:xiangshan-nanhu",
            "uarch:nonexistent",
        )
        assert not store.is_entity_related_to(
            "uarch:nonexistent",
            "cpu:xiangshan-nanhu",
        )

        assert not store.is_entity_related_to("device:sipeed-lpi4a", "arch:riscv64")
        assert store.is_entity_related_to(
            "device:sipeed-lpi4a",
            "arch:riscv64",
            transitive=True,
        )
        assert store.is_entity_related_to(
            "arch:riscv64",
            "device:sipeed-lpi4a",
            transitive=True,
        )
        assert not store.is_entity_related_to(
            "uarch:xiangshan-nanhu",
            "device:sipeed-lpi4a",
            transitive=True,
        )
        assert not store.is_entity_related_to(
            "device:sipeed-lpi4a",
            "uarch:xiangshan-nanhu",
            transitive=True,
        )
        assert store.is_entity_related_to(
            "device:sipeed-lpi4a",
            "uarch:xiangshan-nanhu",
            unidirectional=False,
            transitive=True,
        )
        assert store.is_entity_related_to(
            "uarch:xiangshan-nanhu",
            "device:sipeed-lpi4a",
            unidirectional=False,
            transitive=True,
        )
