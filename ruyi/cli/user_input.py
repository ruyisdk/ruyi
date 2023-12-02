from .. import log


def ask_for_yesno_confirmation(prompt: str, default: bool = False) -> bool:
    choices_help = "(Y/n)" if default else "(y/N)"

    while True:
        try:
            user_input = input(f"{prompt} {choices_help} ")
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
