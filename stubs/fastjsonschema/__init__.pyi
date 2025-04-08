from typing import Callable, Mapping

from .exceptions import (
    JsonSchemaDefinitionException as JsonSchemaDefinitionException,
    JsonSchemaException as JsonSchemaException,
    JsonSchemaValueException as JsonSchemaValueException,
)
from .version import VERSION as VERSION

__all__ = [
    "VERSION",
    "JsonSchemaException",
    "JsonSchemaValueException",
    "JsonSchemaDefinitionException",
    "validate",
    "compile",
    "compile_to_code",
]

def validate(
    definition: object,
    data: object,
    handlers: Mapping[str, Callable[[str], object]] = {},
    formats: Mapping[str, str | Callable[[object], bool]] = {},
    use_default: bool = True,
    use_formats: bool = True,
    detailed_exceptions: bool = True,
): ...
def compile(
    definition: object,
    handlers: Mapping[str, Callable[[str], object]] = {},
    formats: Mapping[str, str | Callable[[object], bool]] = {},
    use_default: bool = True,
    use_formats: bool = True,
    detailed_exceptions: bool = True,
) -> Callable[[object], object | None]: ...
def compile_to_code(
    definition: object,
    handlers: Mapping[str, Callable[[str], object]] = {},
    formats: Mapping[str, str | Callable[[object], bool]] = {},
    use_default: bool = True,
    use_formats: bool = True,
    detailed_exceptions: bool = True,
) -> str: ...
