from ruyi.utils.l10n import lang_code_to_lang_region, LangAndRegion, match_lang_code


def test_lang_code_to_lang_region() -> None:
    assert lang_code_to_lang_region("en", False) == LangAndRegion("en", "en", None)
    assert lang_code_to_lang_region("en", True) == LangAndRegion("en", "en", "US")
    assert lang_code_to_lang_region("en_SG", False) == LangAndRegion(
        "en_SG", "en", "SG"
    )
    assert lang_code_to_lang_region("zh", False) == LangAndRegion("zh", "zh", None)
    assert lang_code_to_lang_region("zh", True) == LangAndRegion("zh", "zh", "CN")
    assert lang_code_to_lang_region("zh_HK", False) == LangAndRegion(
        "zh_HK", "zh", "HK"
    )
    assert lang_code_to_lang_region("cmn", False) == LangAndRegion("cmn", "cmn", None)
    assert lang_code_to_lang_region("cmn", True) == LangAndRegion("cmn", "cmn", None)


def test_match_lang_code() -> None:
    assert match_lang_code("zh", ["en"]) == "en"
    assert match_lang_code("en_US", ["en"]) == "en"
    assert match_lang_code("en", ["en_US"]) == "en_US"
    assert match_lang_code("en_US", ["en_US"]) == "en_US"

    assert match_lang_code("zh", ["en", "zh"]) == "zh"
    assert match_lang_code("zh", ["en", "zh_CN"]) == "zh_CN"
    assert match_lang_code("zh", ["en", "zh_HK"]) == "zh_HK"
    assert match_lang_code("zh_HK", ["en", "zh_CN"]) == "zh_CN"
    assert match_lang_code("zh_CN", ["en", "zh_HK"]) == "zh_HK"

    # match according to region
    assert match_lang_code("ga", ["en", "en_IE", "zh_CN"]) == "en_IE"

    # match according to language
    assert match_lang_code("pt", ["pt_BR", "en", "zh"]) == "pt_BR"

    # fallback in the order of en_US, en_*, zh_CN, zh_*
    assert (
        match_lang_code("pt", ["ga", "zh_HK", "zh", "zh_CN", "en_IE", "en", "en_US"])
        == "en_US"
    )
    assert match_lang_code("pt", ["ga", "zh_HK", "zh", "zh_CN", "en_IE", "en"]) == "en"
    assert match_lang_code("pt", ["ga", "zh_HK", "zh", "zh_CN", "en_IE"]) == "en_IE"
    assert match_lang_code("pt", ["ga", "zh_HK", "zh", "zh_CN"]) == "zh_CN"
    assert match_lang_code("pt", ["ga", "zh_HK", "zh"]) == "zh"
    assert match_lang_code("pt", ["ga", "zh_HK"]) == "zh_HK"

    # fallback to the lexicographically first one
    assert match_lang_code("ru", ["ga", "es_ES"]) == "es_ES"
    assert match_lang_code("ru", ["es_ES", "ga"]) == "es_ES"
