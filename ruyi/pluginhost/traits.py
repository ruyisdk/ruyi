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


class SupportsMessageStore(Protocol):
    def get_message_template(self, msgid: str, lang_code: str) -> str | None: ...

    def render_message(
        self,
        msgid: str,
        lang_code: str,
        params: dict[str, str],
        add_trailing_newline: bool = False,
    ) -> str: ...
