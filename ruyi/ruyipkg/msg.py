from typing import Callable, TypedDict, TypeGuard, cast

from jinja2 import BaseLoader, Environment, TemplateNotFound

from ..utils.l10n import match_lang_code


RepoMessagesV1Type = TypedDict(
    "RepoMessagesV1Type",
    {
        "ruyi-repo-messages": str,
        # lang_code: message_content
    },
)


def validate_repo_messages_v1(x: object) -> TypeGuard[RepoMessagesV1Type]:
    if not isinstance(x, dict):
        return False
    x = cast(dict[str, object], x)
    if x.get("ruyi-repo-messages", "") != "v1":
        return False
    return True


def group_messages_by_lang_code(decl: RepoMessagesV1Type) -> dict[str, dict[str, str]]:
    obj = cast(dict[str, dict[str, str]], decl)

    result: dict[str, dict[str, str]] = {}
    for msgid, msg_decl in obj.items():
        # skip the file type marker
        if msgid == "ruyi-repo-messages":
            continue

        for lang_code, msg in msg_decl.items():
            if lang_code not in result:
                result[lang_code] = {}
            result[lang_code][msgid] = msg

    return result


class RepoMessageStore:
    def __init__(self, decl: RepoMessagesV1Type) -> None:
        self._msgs_by_lang_code = group_messages_by_lang_code(decl)
        self._cached_envs_by_lang_code: dict[str, Environment] = {}

    @classmethod
    def from_object(cls, obj: object) -> "RepoMessageStore":
        if not validate_repo_messages_v1(obj):
            # TODO: more detail in the error message
            raise RuntimeError("malformed v1 repo messages definition")
        return cls(obj)

    def get_message_template(self, msgid: str, lang_code: str) -> str | None:
        resolved_lang_code = match_lang_code(lang_code, self._msgs_by_lang_code.keys())
        return self._msgs_by_lang_code[resolved_lang_code].get(msgid)

    def get_jinja(self, lang_code: str) -> Environment:
        if lang_code in self._cached_envs_by_lang_code:
            return self._cached_envs_by_lang_code[lang_code]

        env = Environment(
            loader=RepoMessageLoader(self, lang_code),
            autoescape=False,  # we're not producing HTML
            auto_reload=False,  # we're serving static assets
        )
        self._cached_envs_by_lang_code[lang_code] = env
        return env

    def render_message(
        self,
        msgid: str,
        lang_code: str,
        params: dict[str, str],
        add_trailing_newline: bool = False,
    ) -> str:
        env = self.get_jinja(lang_code)
        tmpl = env.get_template(msgid)
        result = tmpl.render(params)
        if add_trailing_newline and not result.endswith("\n"):
            return result + "\n"
        return result


class RepoMessageLoader(BaseLoader):
    def __init__(self, store: RepoMessageStore, lang_code: str) -> None:
        self.store = store
        self.lang_code = lang_code

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> tuple[str, (str | None), (Callable[[], bool] | None)]:
        result = self.store.get_message_template(template, self.lang_code)
        if result is None:
            raise TemplateNotFound(template)
        return result, None, None
