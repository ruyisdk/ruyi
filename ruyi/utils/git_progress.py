from typing import Any, Self

from git.remote import RemoteProgress
import tqdm

from .. import log


def is_phase_beginning(op: int) -> bool:
    return op & RemoteProgress.BEGIN != 0


def is_phase_ending(op: int) -> bool:
    return op & RemoteProgress.END != 0


def get_phase_name(op: int) -> str:
    match op & RemoteProgress.OP_MASK:
        case RemoteProgress.COUNTING:
            return "Counting"
        case RemoteProgress.COMPRESSING:
            return "Compressing"
        case RemoteProgress.WRITING:
            return "Writing"
        case RemoteProgress.RECEIVING:
            return "Receiving"
        case RemoteProgress.RESOLVING:
            return "Resolving"
        case RemoteProgress.FINDING_SOURCES:
            return "Finding sources"
        case RemoteProgress.CHECKING_OUT:
            return "Checking out"
        case _:
            return f"GitPython phase {op}"


class TqdmGitProgress(RemoteProgress):
    def __init__(self) -> None:
        super().__init__()
        self.tq: tqdm.tqdm[Any] | None = None
        self.last = 0.0

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, tb: Any) -> None:
        self._stop()

    def _start(self, op: int, max_count: float | None) -> None:
        self.tq = tqdm.tqdm(desc=get_phase_name(op), total=max_count)
        self.last = 0.0

    def _stop(self) -> None:
        if self.tq is None:
            return
        self.tq.close()
        self.tq = None

    def _bump_to(self, val: float) -> None:
        if self.tq is None:
            return
        incr = val - self.last
        self.tq.update(incr)
        self.last = val

    def update(
        self,
        op_code: int,
        cur_count: str | float,
        max_count: str | float | None = None,
        message: str = "",
    ) -> None:
        cur_count = cur_count if isinstance(cur_count, float) else 0.0
        max_count = max_count if isinstance(max_count, float) else None
        if is_phase_beginning(op_code):
            if message:
                log.I(message)
            self._start(op_code, max_count)
        elif is_phase_ending(op_code):
            self._stop()
        else:
            self._bump_to(cur_count)
