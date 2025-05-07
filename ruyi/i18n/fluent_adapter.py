from typing import Generator

from fluent.runtime import AbstractResourceLoader
from fluent.syntax import FluentParser
from fluent.syntax.ast import Resource


class PrebuiltFluentResourceLoader(AbstractResourceLoader):
    def __init__(self, data: dict[str, str]) -> None:
        self._data = data

    @classmethod
    def _resource_key(cls, resource_id: str, locale: str) -> str:
        return f"{resource_id}@{locale}"

    def resources(
        self,
        locale: str,
        resource_ids: list[str],
    ) -> Generator[list[Resource], None, None]:
        resources: list[Resource] = []
        for resource_id in resource_ids:
            # combine resource_id and locale
            if content := self._data.get(self._resource_key(resource_id, locale)):
                resources.append(FluentParser().parse(content))
        if resources:
            yield resources
