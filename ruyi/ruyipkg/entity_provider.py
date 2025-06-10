import abc
import json
import os
import pathlib
import sys
from typing import Any, Mapping, Sequence

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from ..log import RuyiLogger
from ..utils.porcelain import PorcelainEntity, PorcelainEntityType


class PorcelainEntityListOutputV1(PorcelainEntity):
    entity_type: str
    entity_id: str
    display_name: str | None
    data: Mapping[str, Any]
    related_refs: list[str]
    reverse_refs: list[str]


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

    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        data: Mapping[str, Any],
    ) -> None:
        self._entity_type = entity_type
        self._id = entity_id
        self._data = data

        self._reverse_refs: set[str] = set()

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
    def unique_among_type_during_traversal(self) -> bool:
        """Whether the entity should be unique among all entities of the same type
        during traversal.

        For example, if the entity is ``arch:foo64`` and there is also ``arch:foo32``,
        with this property set to ``True`` on each, there will be only one
        ``arch:foo*`` entity in any traversal path involving them, so that a
        hypothetical traversal starting from a "foo64" device will not return
        entities only related to the "foo32" architecture.
        """

        if r := self._data.get("unique_among_type_during_traversal", None):
            if isinstance(r, bool):
                return r
        # return False if type is unexpected
        return False

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

    @property
    def reverse_refs(self) -> list[str]:
        """Get the list of reverse-related entity references."""
        return list(self._reverse_refs)

    def _add_reverse_ref(self, ref: str) -> None:
        self._reverse_refs.add(ref)

    def to_porcelain(self) -> PorcelainEntityListOutputV1:
        """Convert this entity to porcelain output format."""

        return {
            "ty": PorcelainEntityType.EntityListOutputV1,
            "entity_type": self.entity_type,
            "entity_id": self.id,
            "display_name": self.display_name,
            "data": self._data,
            "related_refs": self.related_refs,
            "reverse_refs": self.reverse_refs,
        }

    def __str__(self) -> str:
        return f"{self.entity_type}:{self.id}"

    def __hash__(self) -> int:
        return hash((self.entity_type, self.id))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity):
            return NotImplemented
        return self.entity_type == other.entity_type and self.id == other.id


class BaseEntityProvider(abc.ABC):
    """Abstract base class for entity data providers.

    Entity providers are responsible for discovering and loading entity schemas and data.
    """

    @abc.abstractmethod
    def discover_schemas(self) -> dict[str, object]:
        """Discover available entity schemas.

        Returns:
            A dictionary mapping entity types to their schema objects
        """
        raise NotImplementedError

    @abc.abstractmethod
    def load_entities(
        self,
        entity_types: Sequence[str],
    ) -> Mapping[str, Mapping[str, Mapping[str, Any]]]:
        """Load entities of the given types.

        Args:
            entity_types: Sequence of entity types to load

        Returns:
            A nested dictionary mapping entity types to entity IDs to raw entity data
        """
        raise NotImplementedError


class FSEntityProvider(BaseEntityProvider):
    """Entity provider that loads entity data from the filesystem.

    This provider reads schemas from the ``_schemas`` directory and entity data from
    subdirectories organized by entity type.
    """

    def __init__(self, logger: RuyiLogger, entities_root: os.PathLike[Any]) -> None:
        """Initialize the filesystem-based entity provider.

        Args:
            logger: Logger instance to use.
            entities_root: Path to the root directory containing entity data.
                           The ``_schemas`` directory should be a subdirectory of this path.
        """

        self._logger = logger
        self._entities_root = pathlib.Path(entities_root)
        self._schemas_root = self._entities_root / "_schemas"

    def discover_schemas(self) -> dict[str, object]:
        """Discover entity schemas from the filesystem.

        Returns:
            A dictionary mapping entity types to their schema objects
        """
        schemas: dict[str, object] = {}

        if not os.path.isdir(self._schemas_root):
            self._logger.D(f"entity schemas directory not found: {self._schemas_root}")
            return schemas

        try:
            schema_files = list(self._schemas_root.glob("*.jsonschema"))
        except IOError as e:
            self._logger.W(
                f"failed to access entity schemas directory {self._schemas_root}: {e}"
            )
            return schemas

        for p in schema_files:
            # Extract entity type from schema filename (remove .jsonschema extension)
            entity_type = p.name[:-11]  # 11 is the length of ".jsonschema"

            try:
                with open(p, "r", encoding="utf-8") as f:
                    schema = json.load(f)
            except (IOError, json.JSONDecodeError) as e:
                self._logger.D(
                    f"failed to load schema for entity type '{entity_type}': {e}"
                )
                continue

            # Cache the schema
            schemas[entity_type] = schema

        self._logger.D(f"discovered entity types from schemas: {list(schemas.keys())}")
        return schemas

    def load_entities(
        self,
        entity_types: Sequence[str],
    ) -> Mapping[str, Mapping[str, Mapping[str, Any]]]:
        """Load entity data from the filesystem.

        Args:
            entity_types: Set of entity types to load

        Returns:
            A nested dictionary mapping entity types to entity IDs to raw entity data
        """
        entities: dict[str, dict[str, dict[str, Any]]] = {
            entity_type: {} for entity_type in entity_types
        }

        for entity_type in entity_types:
            type_dir = self._entities_root / entity_type

            if not type_dir.exists():
                self._logger.D(f"entity type directory does not exist: {type_dir}")
                continue

            for file_path in type_dir.glob("*.toml"):
                try:
                    with open(file_path, "rb") as f:
                        data = tomllib.load(f)
                except (IOError, tomllib.TOMLDecodeError) as e:
                    self._logger.W(f"failed to load entity from {file_path}: {e}")
                    continue

                # Extract entity ID from filename (remove .toml extension)
                entity_id = file_path.name[:-5]

                # Create and store raw entity data
                entities[entity_type][entity_id] = data

        entity_counts = {t: len(e) for t, e in entities.items()}
        self._logger.D(f"count of loaded entities from filesystem: {entity_counts}")
        return entities
