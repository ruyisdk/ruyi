import os
import pathlib
import tomllib
import json
from typing import Any, Callable, Iterator

import fastjsonschema
from fastjsonschema.exceptions import JsonSchemaException

from .. import log


class EntityError(Exception):
    """Base exception for entity-related errors."""

    pass


class EntityValidationError(EntityError):
    """Exception raised when an entity fails validation."""

    def __init__(self, entity_type: str, entity_id: str, cause: Exception) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.cause = cause
        message = (
            f"Entity validation failed for entity '{entity_type}:{entity_id}': {cause}"
        )
        super().__init__(message)


class BaseEntity:
    """Base class for all entity types."""

    def __init__(self, entity_type: str, entity_id: str, data: dict[str, Any]) -> None:
        self._entity_type = entity_type
        self._id = entity_id
        self._data = data

    @property
    def entity_type(self) -> str:
        """Type of the entity."""
        return self._entity_type

    @property
    def id(self) -> str:
        """ID of the entity."""
        return self._id

    @property
    def display_name(self) -> str | None:
        """Human-readable name of the entity."""
        result = self._data[self.entity_type].get("display_name", None)
        if result is None or isinstance(result, str):
            return result
        # return None if type is unexpected
        return None

    @property
    def data(self) -> Any:
        """Raw data of the entity."""
        return self._data[self.entity_type]

    @property
    def related_refs(self) -> list[str]:
        """Get the list of related entity references."""
        if r := self._data.get("related"):
            if isinstance(r, list):
                return r
        # return empty list if that is the case, or if the type is unexpected
        return []

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.id}"


class EntityStore:
    def __init__(self, entities_root: os.PathLike[Any]) -> None:
        self._entities_root = pathlib.Path(entities_root)
        self._schemas_root = self._entities_root / "_schemas"

        self._entity_types: set[str] = set()
        """Cache of entity types discovered in the repository."""

        self._entities: dict[str, dict[str, BaseEntity]] = {}
        """Cache of loaded entities by type."""

        self._schemas: dict[str, object] = {}
        """Cache of loaded schemas."""

        self._validators: dict[str, Callable[[object], object | None]] = {}
        """Cache of compiled schema validators."""

        self._loaded = False
        self._discovered = False

    def _discover_entity_types(self) -> None:
        """Discover all entity types by examining schema files in the _schemas directory."""

        if self._discovered:
            return

        if not os.path.isdir(self._schemas_root):
            log.D(f"entity schemas directory not found: {self._schemas_root}")
            self._discovered = True
            return

        try:
            schema_files = list(self._schemas_root.glob("*.jsonschema"))
        except IOError as e:
            log.W(
                f"failed to access entity schemas directory {self._schemas_root}: {e}"
            )
            self._discovered = True
            return

        for p in schema_files:
            # Extract entity type from schema filename (remove .jsonschema extension)
            entity_type = p.name[:-11]  # 11 is the length of ".jsonschema"

            try:
                with open(p, "r", encoding="utf-8") as f:
                    schema = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                log.D(f"failed to load schema for entity type '{entity_type}': {e}")
                continue

            # cache the schema
            # validator is created later on demand
            self._schemas[entity_type] = schema
            self._entity_types.add(entity_type)
            self._entities[entity_type] = {}

        log.D(f"discovered entity types from schemas: {self._entity_types}")
        self._discovered = True

    def _get_validator(self, entity_type: str) -> Callable[[object], object | None]:
        """Get or create a compiled schema validator for the entity type."""
        if entity_type in self._validators:
            return self._validators[entity_type]

        schema = self._schemas.get(entity_type)
        if not schema:
            log.W(f"no schema found for entity type: {entity_type}")
            # Return a simple validator that accepts anything
            return lambda x: x

        try:
            validator = fastjsonschema.compile(schema)
            self._validators[entity_type] = validator
            return validator
        except Exception as e:
            log.W(f"failed to compile schema for {entity_type}: {e}")
            # Return a simple validator that accepts anything
            return lambda x: x

    def _validate_entity(
        self,
        entity_type: str,
        entity_id: str,
        data: dict[str, Any],
    ) -> None:
        """Validate an entity against its schema."""
        validator = self._get_validator(entity_type)

        try:
            validator(data)
        except JsonSchemaException as e:
            raise EntityValidationError(entity_type, entity_id, e) from e

    def load_all(self, validate: bool = True) -> None:
        """Load all entities from the repository."""
        if self._loaded:
            return

        # Discover entity types from schemas if not already done
        self._discover_entity_types()

        for entity_type in self._entity_types:
            type_dir = self._entities_root / entity_type

            for file_path in type_dir.glob("*.toml"):
                try:
                    with open(file_path, "rb") as f:
                        data = tomllib.load(f)
                except (IOError, tomllib.TOMLDecodeError) as e:
                    log.W(f"failed to load entity from {file_path}: {e}")
                    continue

                # Extract entity ID from filename (remove .toml extension)
                entity_id = file_path.name[:-5]

                if validate:
                    try:
                        self._validate_entity(entity_type, entity_id, data)
                    except Exception as e:
                        log.W(
                            f"failed to validate entity from {file_path}: {e}\ndata={data}"
                        )
                        continue

                # Create and store a generic entity
                self._entities[entity_type][entity_id] = BaseEntity(
                    entity_type,
                    entity_id,
                    data,
                )

        self._loaded = True
        entity_counts = {t: len(entities) for t, entities in self._entities.items()}
        log.D(f"count of loaded entities: {entity_counts}")

    def get_entity_types(self) -> Iterator[str]:
        """Get all available entity types from the schemas."""
        self._discover_entity_types()
        yield from self._entity_types

    def get_entity(self, entity_type: str, entity_id: str) -> BaseEntity | None:
        """Get an entity by type and ID."""
        self.load_all()
        return self._entities.get(entity_type, {}).get(entity_id)

    def iter_entities(self, entity_type: str | None) -> Iterator[BaseEntity]:
        """Iterate over all entities of a specific type, or all entities."""
        self.load_all()
        if entity_type is not None:
            yield from self._entities.get(entity_type, {}).values()
            return

        for entities in self._entities.values():
            yield from entities.values()

    def get_entity_by_ref(self, ref: str) -> BaseEntity | None:
        """Resolve an entity reference of the form ``type:id``."""

        if ":" not in ref:
            raise ValueError(f"Invalid entity reference: {ref}")
        entity_type, entity_id = ref.split(":", 1)

        self.load_all()
        return self.get_entity(entity_type, entity_id)

    def list_related_entities(self, entity: BaseEntity | str) -> list[BaseEntity]:
        """Get all directly related entities of the given entity.

        Args:
            entity: The entity whose related entities to retrieve, or an entity reference
                    in the form ``type:id``.

        Returns:
            A list of directly related entities
        """

        if isinstance(entity, str):
            e = self.get_entity_by_ref(entity)
            if e is None:
                raise ValueError(f"Entity not found: {entity}")
            entity = e

        related_entities = []
        for ref in entity.related_refs:
            related_entity = self.get_entity_by_ref(ref)
            if related_entity:
                related_entities.append(related_entity)
        return related_entities

    def traverse_related_entities(
        self,
        entity: BaseEntity | str,
        transitive: bool = False,
        entity_types: list[str] | None = None,
    ) -> Iterator[BaseEntity]:
        """Traverse related entities of the given entity.

        Args:
            entity: The starting entity or reference (in the form ``type:id``).
            transitive: If True, traverse the transitive closure of related entities.
                        If False, only traverse direct related entities.
            entity_types: Optional list of entity types to filter by. If provided,
                          only entities of the specified types will be yielded.

        Returns:
            An iterator over the related entities
        """

        if isinstance(entity, str):
            # If a string is provided, resolve it to an entity
            e = self.get_entity_by_ref(entity)
            if e is None:
                raise ValueError(f"Entity not found: {entity}")
            entity = e

        # Dictionary to track visited entities and avoid cycles
        visited = set()

        # Helper function for recursive traversal
        def _traverse(current_entity: BaseEntity) -> Iterator[BaseEntity]:
            # Skip if already visited (prevents cycles)
            entity_key = f"{current_entity.entity_type}:{current_entity.id}"
            if entity_key in visited:
                return

            # Mark as visited
            visited.add(entity_key)

            # Process related entities
            for related_entity in self.list_related_entities(current_entity):
                # Check if this entity matches the desired type filter
                if entity_types is None or related_entity.entity_type in entity_types:
                    yield related_entity

                # Recursively traverse if transitive mode is enabled
                if transitive:
                    yield from _traverse(related_entity)

        # Start traversal from the given entity
        yield from _traverse(entity)
