"""
VMware vSphere Metrics Q&A — CLI (no API key)

Same architecture as agent.py, but answers via the `claude` command-line tool instead
of the Anthropic API:
- Haiku router selects relevant chapters per question
- Sonnet answers with the selected chapters + skills

Requires the `claude` CLI (Claude Code) to be installed and logged in. No
ANTHROPIC_API_KEY is needed.

Usage:
    python3 agent_claude.py                       # interactive
    python3 agent_claude.py -q "What is CPU Ready?"   # single question
    python3 agent_claude.py -q "..." --no-route   # send the whole book (skip routing)
"""
import argparse
import sys

import claude_backend
from qa_common import (
    ROUTER_PROMPT,
    SYSTEM_PROMPT,
    build_book_excerpt,
    load_chapters,
    parse_chapter_selection,
)
from skills_loader import load_skills, skill_dirs

ANSWER_MODEL = "sonnet"
ROUTER_MODEL = "haiku"


def route_question(question: str, index_txt: str, chapters: dict, titles: list) -> list:
    """Use the claude CLI (Haiku) to pick relevant chapters; fall back to all on error."""
    try:
        reply = claude_backend.complete(
            question,
            system=ROUTER_PROMPT.format(chapter_index=index_txt),
            model=ROUTER_MODEL,
            timeout=120,
        )
    except claude_backend.ClaudeError as e:
        print(f"  [router failed, using all chapters: {e}]")
        return titles
    return parse_chapter_selection(reply, chapters, titles)


def build_system(selected: list, chapters: dict, skills_content: str) -> str:
    """Assemble the full system prompt: persona + skills + selected book chapters."""
    book_excerpt = build_book_excerpt(selected, chapters)
    return (
        SYSTEM_PROMPT
        + skills_content
        + f"\n\n## Book Chapters: {', '.join(selected)}\n\n{book_excerpt}"
    )


def answer(question: str, chapters: dict, index_txt: str, titles: list,
           skills_content: str, route: bool = True) -> str:
    """Route, then ask the claude CLI for an answer. Prints and returns it."""
    selected = route_question(question, index_txt, chapters, titles) if route else titles
    system = build_system(selected, chapters, skills_content)
    print(f"  [router: {selected} — system ~{len(system) // 4:,} tokens]")
    print("\nAssistant: ", end="", flush=True)
    try:
        reply = claude_backend.complete(question, system=system, model=ANSWER_MODEL)
    except claude_backend.ClaudeError as e:
        print(f"\nError: {e}\n")
        return ""
    print(reply + "\n")
    return reply


def interactive(chapters, index_txt, titles, skills_content, route):
    print("\nAsk me anything about VMware vSphere metrics! (no API key — using the claude CLI)")
    print("Type 'quit' to exit.\n")
    print("Note: each question is answered independently (no multi-turn memory).\n")
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break
        answer(question, chapters, index_txt, titles, skills_content, route=route)


def main():
    parser = argparse.ArgumentParser(
        description="VMware vSphere Metrics Q&A — claude CLI backend (no API key)"
    )
    parser.add_argument("--question", "-q", help="Question to ask (non-interactive)")
    parser.add_argument("--no-route", action="store_true",
                        help="Skip chapter routing; send the whole book as context")
    args = parser.parse_args()

    if not claude_backend.claude_available():
        print("Error: the `claude` CLI was not found on PATH.")
        print("Install Claude Code and run `claude` once to log in: https://claude.com/claude-code")
        sys.exit(1)

    print("Loading chapters...")
    chapters, index_txt, titles = load_chapters()
    total_tokens = sum(len(c) // 4 for c in chapters.values())
    print(f"Loaded {len(chapters)} chapters (~{total_tokens:,} total tokens)")

    skills_content = load_skills()
    print(f"Loaded {len(skill_dirs())} skills: {', '.join(skill_dirs())}")
    print(f"Backend: claude CLI  |  Answer: {ANSWER_MODEL}  |  Router: {ROUTER_MODEL}")

    route = not args.no_route
    if args.question:
        answer(args.question, chapters, index_txt, titles, skills_content, route=route)
    else:
        interactive(chapters, index_txt, titles, skills_content, route)


if __name__ == "__main__":
    main()
