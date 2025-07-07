import os


class NewsReadStatusStore:
    def __init__(self, path: str) -> None:
        self._path = path
        self._status: set[str] = set()
        self._orig_status: set[str] = set()

    def load(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8") as fp:
                for line in fp:
                    self._orig_status.add(line.strip())
        except FileNotFoundError:
            return

        self._status = self._orig_status.copy()

    def __contains__(self, key: str) -> bool:
        return key in self._status

    def add(self, id: str) -> None:
        return self._status.add(id)

    def save(self) -> None:
        if self._status == self._orig_status:
            return

        content = "".join(f"{id}\n" for id in self._status)
        with open(self._path, "w", encoding="utf-8") as fp:
            fp.write(content)

    def remove(self) -> None:
        try:
            os.unlink(self._path)
        except FileNotFoundError:
            # nothing to remove, that's fine
            pass
