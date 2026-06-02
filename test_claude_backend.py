"""
Tests for claude_backend.py (argv construction + error handling).

These do NOT invoke the claude CLI — they only check argv building and the missing-CLI
error path, so they run anywhere.

Run with: pytest test_claude_backend.py   or   python3 test_claude_backend.py
"""
import claude_backend


def test_build_argv_minimal():
    argv = claude_backend.build_argv()
    assert argv == ["claude", "-p"]


def test_build_argv_with_model_and_system_and_format():
    argv = claude_backend.build_argv(
        system_file="/tmp/sys.txt", model="sonnet", output_format="json"
    )
    assert argv[:2] == ["claude", "-p"]
    assert "--model" in argv and argv[argv.index("--model") + 1] == "sonnet"
    assert "--system-prompt-file" in argv
    assert argv[argv.index("--system-prompt-file") + 1] == "/tmp/sys.txt"
    assert "--output-format" in argv and argv[argv.index("--output-format") + 1] == "json"


def test_build_argv_text_format_is_omitted():
    # "text" is the CLI default, so we don't pass --output-format for it.
    argv = claude_backend.build_argv(output_format="text")
    assert "--output-format" not in argv


def test_build_argv_never_contains_prompt():
    # The prompt is sent over stdin, never as an argv element.
    argv = claude_backend.build_argv(system_file="/tmp/s", model="haiku")
    assert all("?" not in a for a in argv)  # sanity: no question text leaked in


def test_claude_available_returns_bool():
    assert isinstance(claude_backend.claude_available(), bool)


def test_complete_raises_when_cli_missing():
    original = claude_backend.claude_path
    claude_backend.claude_path = lambda: None  # simulate missing CLI
    try:
        raised = False
        try:
            claude_backend.complete("hi", system="sys", model="haiku")
        except claude_backend.ClaudeError:
            raised = True
        assert raised, "complete() should raise ClaudeError when claude is not on PATH"
    finally:
        claude_backend.claude_path = original


if __name__ == "__main__":
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(funcs) - failed}/{len(funcs)} passed")
    raise SystemExit(1 if failed else 0)
