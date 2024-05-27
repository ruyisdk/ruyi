import os.path

from .. import log


def ask_for_yesno_confirmation(prompt: str, default: bool = False) -> bool:
    choices_help = "(Y/n)" if default else "(y/N)"

    while True:
        try:
            log.stdout(f"{prompt} {choices_help} ", end='')
            user_input = input()
        except EOFError:
            yesno = "YES" if default else "NO"
            log.W(f"EOF while reading user input, assuming the default choice {yesno}")
            return default

        if not user_input:
            return default
        if user_input in {"Y", "y", "yes"}:
            return True
        if user_input in {"N", "n", "no"}:
            return False
        else:
            log.stdout(f"Unrecognized input [yellow]'{user_input}'[/yellow].")
            log.stdout("Accepted choices: Y/y/yes for YES, N/n/no for NO.")


def ask_for_kv_choice(prompt: str, choices_kv: dict[str, str]) -> str:
    choices_kv_list = list(choices_kv.items())
    choices_prompts = [i[1] for i in choices_kv_list]
    choice = ask_for_choice(prompt, choices_prompts)
    return choices_kv_list[choice][0]


def ask_for_choice(prompt: str, choices_texts: list[str]) -> int:
    log.stdout(prompt, end="\n\n")
    for i, choice_text in enumerate(choices_texts):
        log.stdout(f"  {i + 1}. {choice_text}")

    log.stdout("")

    nr_choices = len(choices_texts)
    choices_help = f"(1-{nr_choices})"
    while True:
        try:
            user_input = input(f"Choice? {choices_help} ")
        except EOFError:
            raise ValueError("EOF while reading user choice")

        try:
            choice_int = int(user_input)
        except ValueError:
            log.stdout(f"Unrecognized input [yellow]'{user_input}'[/yellow].")
            log.stdout(
                f"Accepted choices: an integer number from 1 to {nr_choices} inclusive."
            )
            continue

        if 1 <= choice_int <= nr_choices:
            return choice_int - 1

        log.stdout(f"Out-of-range input [yellow]'{user_input}'[/yellow].")
        log.stdout(
            f"Accepted choices: an integer number from 1 to {nr_choices} inclusive."
        )


def ask_for_file(prompt: str) -> str:
    while True:
        try:
            user_input = input(f"{prompt} ")
        except EOFError:
            raise ValueError("EOF while reading user input")

        if os.path.exists(user_input):
            return user_input

        log.stdout(
            f"[yellow]'{user_input}'[/yellow] is not a path to an existing file."
        )
