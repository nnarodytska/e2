"""
Backend that talks to the `claude` CLI (Claude Code) instead of the Anthropic API.

This needs no ANTHROPIC_API_KEY — it reuses whatever login the `claude` command is
authenticated with (e.g. a Claude subscription). The large book context is passed via a
temporary --system-prompt-file (no argv size limit) and the question is fed over stdin.

Stdlib only.
"""
import os
import shutil
import subprocess
import tempfile

CLAUDE_BIN = "claude"


class ClaudeError(RuntimeError):
    """Raised when the claude CLI is missing or returns a non-zero exit code."""


def claude_path() -> str | None:
    """Absolute path to the claude binary, or None if not on PATH."""
    return shutil.which(CLAUDE_BIN)


def claude_available() -> bool:
    return claude_path() is not None


def build_argv(
    *,
    system_file: str | None = None,
    model: str | None = None,
    output_format: str = "text",
) -> list[str]:
    """Build the argv for a non-interactive `claude -p` call.

    The prompt itself is NOT included here — it is sent over stdin by complete() to avoid
    argv size limits and mis-parsing of prompts that start with '-'.
    """
    argv = [CLAUDE_BIN, "-p"]
    if model:
        argv += ["--model", model]
    if system_file:
        argv += ["--system-prompt-file", system_file]
    if output_format and output_format != "text":
        argv += ["--output-format", output_format]
    return argv


def complete(prompt: str, system: str, *, model: str = "sonnet", timeout: int = 300) -> str:
    """Run one non-interactive completion through the claude CLI and return the text.

    `system` fully replaces the default Claude Code system prompt (so the model takes on
    our vSphere-advisor persona and book context instead of the coding-agent persona).
    """
    if not claude_available():
        raise ClaudeError(
            f"`{CLAUDE_BIN}` not found on PATH. Install Claude Code and run `claude` once "
            "to log in (https://claude.com/claude-code)."
        )

    fd, sysfile = tempfile.mkstemp(suffix=".sysprompt.txt")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(system)
        argv = build_argv(system_file=sysfile, model=model)
        try:
            result = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ClaudeError(f"claude CLI timed out after {timeout}s")
        if result.returncode != 0:
            # The CLI prints auth/usage errors to stdout, so fall back to it.
            detail = (
                result.stderr.strip()
                or result.stdout.strip()
                or f"claude exited {result.returncode}"
            )
            if "authenticat" in detail.lower() or "401" in detail:
                detail += (
                    "\n  -> The `claude` CLI is not logged in (or its token expired). "
                    "Run `claude` once interactively to log in, then retry."
                )
            raise ClaudeError(detail)
        return result.stdout.strip()
    finally:
        os.unlink(sysfile)
