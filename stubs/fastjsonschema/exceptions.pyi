import re

SPLIT_RE: re.Pattern[str]

class JsonSchemaException(ValueError): ...

class JsonSchemaValueException(JsonSchemaException):
    message: str
    value: object | None
    name: str | None
    definition: object | None
    rule: str | None
    def __init__(
        self,
        message: str,
        value: object | None = None,
        name: str | None = None,
        definition: object | None = None,
        rule: str | None = None,
    ) -> None: ...
    @property
    def path(self) -> list[str]: ...
    @property
    def rule_definition(self) -> object: ...

class JsonSchemaDefinitionException(JsonSchemaException): ...
