from typing import Protocol


class SupportsGetOption(Protocol):
    def get_option(self, key: str) -> object: ...


class SupportsEvalFunction(Protocol):
    def eval_function(
        self,
        function: object,
        *args: object,
        **kwargs: object,
    ) -> object: ...
