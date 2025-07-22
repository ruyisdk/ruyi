import os.path

from ..log import RuyiLogger


def pause_before_continuing(
    logger: RuyiLogger,
) -> None:
    """Pause and wait for the user to press Enter before continuing.

    EOFError should be handled by the caller."""

    logger.stdout("Press [green]<ENTER>[/] to continue: ", end="")
    input()


def ask_for_yesno_confirmation(
    logger: RuyiLogger,
    prompt: str,
    default: bool = False,
) -> bool:
    choices_help = "(Y/n)" if default else "(y/N)"

    while True:
        try:
            logger.stdout(f"{prompt} {choices_help} ", end="")
            user_input = input()
        except EOFError:
            yesno = "YES" if default else "NO"
            logger.W(
                f"EOF while reading user input, assuming the default choice {yesno}"
            )
            return default

        if not user_input:
            return default
        if user_input in {"Y", "y", "yes"}:
            return True
        if user_input in {"N", "n", "no"}:
            return False
        else:
            logger.stdout(f"Unrecognized input [yellow]'{user_input}'[/].")
            logger.stdout("Accepted choices: Y/y/yes for YES, N/n/no for NO.")


def ask_for_kv_choice(
    logger: RuyiLogger,
    prompt: str,
    choices_kv: dict[str, str],
    default_key: str | None = None,
) -> str:
    choices_kv_list = list(choices_kv.items())
    choices_prompts = [i[1] for i in choices_kv_list]

    default_idx: int | None = None
    if default_key is not None:
        for i, k in enumerate(choices_kv_list):
            if k[0] == default_key:
                default_idx = i
                break
        if default_idx is None:
            raise ValueError(f"Default choice key '{default_key}' not in choices")

    choice = ask_for_choice(logger, prompt, choices_prompts, default_idx)
    return choices_kv_list[choice][0]


def ask_for_choice(
    logger: RuyiLogger,
    prompt: str,
    choices_texts: list[str],
    default_idx: int | None = None,
) -> int:
    logger.stdout(prompt, end="\n\n")
    for i, choice_text in enumerate(choices_texts):
        logger.stdout(f"  {i + 1}. {choice_text}")

    logger.stdout("")

    nr_choices = len(choices_texts)
    if default_idx is not None:
        if not (0 <= default_idx < nr_choices):
            raise ValueError(f"Default choice index {default_idx} out of range")
        choices_help = f"(1-{nr_choices}, default {default_idx + 1})"
    else:
        choices_help = f"(1-{nr_choices})"
    while True:
        try:
            user_input = input(f"Choice? {choices_help} ")
        except EOFError:
            raise ValueError("EOF while reading user choice")

        if default_idx is not None and not user_input:
            return default_idx

        try:
            choice_int = int(user_input)
        except ValueError:
            logger.stdout(f"Unrecognized input [yellow]'{user_input}'[/].")
            logger.stdout(
                f"Accepted choices: an integer number from 1 to {nr_choices} inclusive."
            )
            continue

        if 1 <= choice_int <= nr_choices:
            return choice_int - 1

        logger.stdout(f"Out-of-range input [yellow]'{user_input}'[/].")
        logger.stdout(
            f"Accepted choices: an integer number from 1 to {nr_choices} inclusive."
        )


def ask_for_file(
    logger: RuyiLogger,
    prompt: str,
) -> str:
    while True:
        try:
            user_input = input(f"{prompt} ")
        except EOFError:
            raise ValueError("EOF while reading user input")

        if os.path.exists(user_input):
            return user_input

        logger.stdout(f"[yellow]'{user_input}'[/] is not a path to an existing file.")
