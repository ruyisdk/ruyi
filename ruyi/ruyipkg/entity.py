from typing import Any, Callable, Iterable, Iterator, Mapping

import fastjsonschema
from fastjsonschema.exceptions import JsonSchemaException

from ..log import RuyiLogger
from .entity_provider import BaseEntity, BaseEntityProvider, EntityValidationError


class EntityStore:
    def __init__(
        self,
        logger: RuyiLogger,
        *providers: BaseEntityProvider,
    ) -> None:
        """Initialize the entity store.

        Args:
            logger: The logger to use.
            providers: A list of entity providers to use for loading entity data.
        """
        self._logger = logger
        self._providers = providers

        self._entity_types: set[str] = set()
        """Cache of entity types discovered."""

        self._entities: dict[str, dict[str, BaseEntity]] = {}
        """Cache of loaded entities by type."""

        self._schemas: dict[str, object] = {}
        """Cache of loaded schemas."""

        self._validators: dict[str, Callable[[object], object | None]] = {}
        """Cache of compiled schema validators."""

        self._loaded = False
        self._discovered = False

    def _discover_entity_types(self) -> None:
        """Discover all entity types by examining schemas from all providers."""
        if self._discovered:
            return

        # Collect schemas from all providers
        for provider in self._providers:
            schemas = provider.discover_schemas()

            # Add new schemas to our cache
            for entity_type, schema in schemas.items():
                if entity_type not in self._schemas:
                    self._schemas[entity_type] = schema
                    self._entity_types.add(entity_type)
                    self._entities[entity_type] = {}

        self._logger.D(f"discovered entity types from schemas: {self._entity_types}")
        self._discovered = True

    def _get_validator(self, entity_type: str) -> Callable[[object], object | None]:
        """Get or create a compiled schema validator for the entity type."""
        if entity_type in self._validators:
            return self._validators[entity_type]

        schema = self._schemas.get(entity_type)
        if not schema:
            self._logger.W(f"no schema found for entity type: {entity_type}")
            # Return a simple validator that accepts anything
            return lambda x: x

        try:
            validator = fastjsonschema.compile(schema)
            self._validators[entity_type] = validator
            return validator
        except Exception as e:
            self._logger.W(f"failed to compile schema for {entity_type}: {e}")
            # Return a simple validator that accepts anything
            return lambda x: x

    def _validate_entity(
        self,
        entity_type: str,
        entity_id: str,
        data: Mapping[str, Any],
    ) -> None:
        """Validate an entity against its schema."""
        validator = self._get_validator(entity_type)

        try:
            validator(data)
        except JsonSchemaException as e:
            raise EntityValidationError(entity_type, entity_id, e) from e

    def load_all(self, validate: bool = True) -> None:
        """Load all entities from all providers."""
        if self._loaded:
            return

        # Discover entity types from schemas if not already done
        self._discover_entity_types()

        # Load entities from all providers
        for provider in self._providers:
            provider_entities = provider.load_entities(list(self._entity_types))

            # Merge entities from this provider with our cache
            for entity_type, entities_by_id in provider_entities.items():
                for entity_id, entity_data in entities_by_id.items():
                    # Validate entity data
                    if validate:
                        self._validate_entity(entity_type, entity_id, entity_data)
                    # Create and store a generic entity
                    self._entities[entity_type][entity_id] = BaseEntity(
                        entity_type,
                        entity_id,
                        entity_data,
                    )

        self._loaded = True

        # Populate reverse references
        # This must happen after the loaded flag is set, because the getter
        # is lazy and will infinitely recurse otherwise.
        for entity_type, entities in self._entities.items():
            for entity_id, entity in entities.items():
                # Collect reverse references
                for ref in entity.related_refs:
                    if related_entity := self.get_entity_by_ref(ref):
                        related_entity._add_reverse_ref(str(entity))

        entity_counts = {t: len(entities) for t, entities in self._entities.items()}
        self._logger.D(f"count of loaded entities: {entity_counts}")

    def get_entity_types(self) -> Iterator[str]:
        """Get all available entity types from the schemas."""
        self._discover_entity_types()
        yield from self._entity_types

    def get_entity(self, entity_type: str, entity_id: str) -> BaseEntity | None:
        """Get an entity by type and ID."""
        self.load_all()
        return self._entities.get(entity_type, {}).get(entity_id)

    def iter_entities(
        self,
        entity_type: str | Iterable[str] | None,
    ) -> Iterator[BaseEntity]:
        """Iterate over all entities of a specific type, or all entities."""
        self.load_all()
        if entity_type is not None:
            if isinstance(entity_type, str):
                yield from self._entities.get(entity_type, {}).values()
                return

            # handle multiple entity types
            for et in entity_type:
                yield from self._entities.get(et, {}).values()
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

    def list_related_entities(
        self,
        entity: BaseEntity | str,
        reverse_refs: bool = False,
    ) -> list[BaseEntity]:
        """Get all directly related entities of the given entity.

        Args:
            entity: The entity whose related entities to retrieve, or an entity reference
                    in the form ``type:id``.
            reverse_refs: If True, return reverse references instead of forward references.

        Returns:
            A list of directly related entities
        """

        if isinstance(entity, str):
            e = self.get_entity_by_ref(entity)
            if e is None:
                raise ValueError(f"Entity not found: {entity}")
            entity = e

        related_entities = []
        for ref in entity.reverse_refs if reverse_refs else entity.related_refs:
            related_entity = self.get_entity_by_ref(ref)
            if related_entity:
                related_entities.append(related_entity)
        return related_entities

    def traverse_related_entities(
        self,
        entity: BaseEntity | str,
        transitive: bool = False,
        no_direct_refs: bool = False,
        forward_refs: bool = True,
        reverse_refs: bool = False,
        entity_types: list[str] | None = None,
    ) -> Iterator[BaseEntity]:
        """Traverse related entities of the given entity.

        Args:
            entity: The starting entity or reference (in the form ``type:id``).
            transitive: If True, traverse the transitive closure of related entities.
                        If False, only traverse direct related entities.
            no_direct_refs: If True, skip direct references.
            forward_refs: If True, traverse forward references.
            reverse_refs: If True, traverse reverse references.
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

        # Set to track visited entities and avoid cycles
        visited = set()

        # Helper function for recursive traversal
        def _traverse(
            current_entity: BaseEntity,
            path: list[BaseEntity],
        ) -> Iterator[BaseEntity]:
            # Skip if already visited (prevents cycles)
            if current_entity in visited:
                return

            # Enforce uniqueness-among-type
            if current_entity.unique_among_type_during_traversal:
                for e in path:
                    if e.entity_type == current_entity.entity_type:
                        return

            depth = len(path)

            # Do not yield related entities if either:
            # - we're the root entity (depth == 0)
            # - no_direct_refs is True and we're at depth == 1
            skip_current_level = depth == 0 or (no_direct_refs and depth == 1)

            # Check if this entity matches the desired type filter
            entity_type_okay = (
                entity_types is None or current_entity.entity_type in entity_types
            )

            if not skip_current_level and entity_type_okay:
                yield current_entity

            # Mark as visited
            visited.add(current_entity)

            new_path = path.copy()
            new_path.append(current_entity)

            # Process forward edges if requested
            if forward_refs:
                for related_entity in self.list_related_entities(
                    current_entity,
                    reverse_refs=False,
                ):
                    # Recursively traverse if transitive mode is enabled
                    # or if we're at the root entity
                    if depth == 0 or transitive:
                        yield from _traverse(related_entity, new_path)

            # Process reverse edges if requested
            if reverse_refs:
                for related_entity in self.list_related_entities(
                    current_entity,
                    reverse_refs=True,
                ):
                    # Recursively traverse if transitive mode is enabled
                    # or if we're at the root entity
                    if depth == 0 or transitive:
                        yield from _traverse(related_entity, new_path)

        # Start traversal from the given entity
        yield from _traverse(entity, [])

    def is_entity_related_to(
        self,
        entity: BaseEntity | str,
        related_entity: BaseEntity | str,
        transitive: bool = False,
        unidirectional: bool = True,
        not_found_ok: bool = True,
    ) -> bool:
        """Check if the given entity is related to another entity.

        Args:
            entity: The starting entity or reference (in the form ``type:id``).
            related_entity: The related entity or reference (in the form ``type:id``).
            transitive: If True, check for transitive relationships.
            unidirectional: If True, entities are considered related if and only if
                            the relationship chain consists of forward or reverse
                            edges only.
            not_found_ok: If True, return False if either entity is not found.
                          If False, raise an error if either entity is not found.

        Returns:
            True if the entities are related, False otherwise.
        """

        if isinstance(entity, str):
            e = self.get_entity_by_ref(entity)
            if e is None:
                if not_found_ok:
                    return False
                raise ValueError(f"Entity not found: {entity}")
            entity = e

        if isinstance(related_entity, str):
            re = self.get_entity_by_ref(related_entity)
            if re is None:
                if not_found_ok:
                    return False
                raise ValueError(f"Entity not found: {related_entity}")
            related_entity = re

        # Check if the two entities are directly related
        if related_entity in self.list_related_entities(entity):
            return True
        if related_entity in self.list_related_entities(entity, reverse_refs=True):
            return True

        # If transitive mode is enabled, check for indirect relationships
        if transitive:
            if unidirectional:
                for e in self.traverse_related_entities(
                    entity,
                    forward_refs=True,
                    reverse_refs=False,
                    transitive=True,
                ):
                    if related_entity in self.list_related_entities(
                        e,
                        reverse_refs=False,
                    ):
                        return True

                for e in self.traverse_related_entities(
                    entity,
                    forward_refs=False,
                    reverse_refs=True,
                    transitive=True,
                ):
                    if related_entity in self.list_related_entities(
                        e,
                        reverse_refs=True,
                    ):
                        return True
            else:
                for e in self.traverse_related_entities(
                    entity,
                    forward_refs=True,
                    reverse_refs=True,
                    transitive=True,
                ):
                    if related_entity in self.list_related_entities(
                        e,
                        reverse_refs=False,
                    ):
                        return True
                    if related_entity in self.list_related_entities(
                        e,
                        reverse_refs=True,
                    ):
                        return True

        return False
