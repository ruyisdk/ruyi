from urllib import parse


def urljoin_for_sure(base: str, url: str) -> str:
    if base.endswith("/"):
        return parse.urljoin(base, url)
    return parse.urljoin(base + "/", url)
