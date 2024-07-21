import locale

from typing import Iterable, NamedTuple


class LangAndRegion(NamedTuple):
    raw: str
    lang: str
    region: str | None


def lang_code_to_lang_region(lang_code: str, guess_region: bool) -> LangAndRegion:
    if not guess_region and "_" not in lang_code:
        return LangAndRegion(lang_code, lang_code, None)

    lang_region_str = locale.normalize(lang_code).split(".")[0]
    parts = lang_region_str.split("_", 2)
    if len(parts) == 1:
        return LangAndRegion(lang_code, lang_region_str, None)
    return LangAndRegion(lang_code, parts[0], parts[1])


def match_lang_code(
    req: str,
    avail: Iterable[str],
) -> str:
    """Returns a proper available language code based on a list of available
    language codes, and a request."""

    if not isinstance(avail, set) or not isinstance(avail, frozenset):
        avail = set(avail)

    # return the only one choice if this is the case
    if len(avail) == 1:
        return next(iter(avail))

    # try exact match
    if req in avail:
        return req

    return _match_lang_code_slowpath(
        lang_code_to_lang_region(req, True),
        [lang_code_to_lang_region(x, False) for x in avail],
    )


def _match_lang_code_slowpath(
    req: LangAndRegion,
    avail: list[LangAndRegion],
) -> str:
    # pick one with the requested region
    if req.region is not None:
        for x in avail:
            if x.region == req.region:
                return x.raw

    # if no match, pick one with the requested language
    for x in avail:
        if x.lang == req.lang:
            return x.raw

    # neither matches, fallback to (en_US, en, en_*, zh_CN, zh, zh_*)
    # in that order
    fallback_en = {x.region: x.raw for x in avail if x.lang == "en"}
    if fallback_en:
        if "US" in fallback_en:
            return fallback_en["US"]
        if None in fallback_en:
            return fallback_en[None]
        return fallback_en[sorted(x for x in fallback_en.keys() if x is not None)[0]]

    fallback_zh = {x.region: x.raw for x in avail if x.lang == "zh"}
    if fallback_zh:
        if "CN" in fallback_zh:
            return fallback_zh["CN"]
        if None in fallback_zh:
            return fallback_zh[None]
        return fallback_zh[sorted(x for x in fallback_zh.keys() if x is not None)[0]]

    # neither en nor zh is available (which is highly unlikely at present)
    # pick the first available one as a last resort
    # sort the list before picking for determinism
    return sorted(x.raw for x in avail)[0]
