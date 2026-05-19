from ruyi.utils.global_mode import is_cli_completion_script_requested


def test_is_cli_completion_script_requested_matches_only_exact_option() -> None:
    assert is_cli_completion_script_requested(["ruyi", "--output-completion-script"])
    assert is_cli_completion_script_requested(
        ["ruyi", "--output-completion-script=bash"]
    )

    assert not is_cli_completion_script_requested(
        ["ruyi", "--output-completion-script-foo"]
    )
    assert not is_cli_completion_script_requested(
        ["ruyi", "--output-completion-script-foo=bash"]
    )
