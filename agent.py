"""
VMware vSphere Metrics Q&A — CLI

Uses the same architecture as the web app:
- Haiku router selects relevant chapters per question
- Sonnet answers with selected chapters + skills
- Streamed output with prompt caching

Image input:
  Interactive:  prefix your message with one or more image paths, one per line:
                  image: /path/to/screenshot.png
                  What metrics are shown here?
  Non-interactive (single question):
                  python3 agent.py --question "..." --image a.png --image b.png
"""

import argparse
import base64
import os

import anthropic
from dotenv import load_dotenv

from qa_common import (
    ROUTER_PROMPT,
    SYSTEM_PROMPT,
    build_book_excerpt,
    load_chapters,
    parse_chapter_selection,
    parse_input,
)
from skills_loader import load_skills, skill_dirs

load_dotenv()

MODEL = "claude-sonnet-4-6"
ROUTER_MODEL = "claude-haiku-4-5-20251001"

# Shared prompts, chapter loading, and input parsing live in qa_common.py.
# Skill loading lives in skills_loader.py: load_skills, skill_dirs.


def load_image(path: str) -> dict:
    """Load an image file and return an Anthropic image content block."""
    ext = os.path.splitext(path)[1].lower()
    media_type_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                      ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_type_map.get(ext, "image/png")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}


def route_question(
    client: anthropic.Anthropic,
    message: str,
    index_txt: str,
    chapters: dict[str, str],
    titles: list[str],
) -> list[str]:
    """Use Haiku to select relevant chapters for the question."""
    prompt = ROUTER_PROMPT.format(chapter_index=index_txt)
    response = client.messages.create(
        model=ROUTER_MODEL,
        max_tokens=200,
        system=prompt,
        messages=[{"role": "user", "content": message}],
    )
    return parse_chapter_selection(response.content[0].text, chapters, titles)


def generate_answer(
    client: anthropic.Anthropic,
    question: str,
    chapters: dict[str, str],
    index_txt: str,
    titles: list[str],
    skills_content: str,
    model: str = MODEL,
    max_tokens: int = 1024,
) -> tuple[list[str], str]:
    """Non-streaming answer: route, then ask the model once. Returns (selected, answer).

    Same prompt construction as ask(), but returns the text instead of streaming — used by
    the API eval harness/tests.
    """
    selected = route_question(client, question, index_txt, chapters, titles)
    book_excerpt = build_book_excerpt(selected, chapters)
    system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT + skills_content,
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": f"## Book Chapters: {', '.join(selected)}\n\n{book_excerpt}"},
    ]
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": question}],
    )
    return selected, response.content[0].text


def build_user_content(text: str, image_paths: list[str]) -> list[dict] | str:
    """Build the content block(s) for a user message."""
    if not image_paths:
        return text
    content = []
    for path in image_paths:
        if not os.path.exists(path):
            print(f"  Warning: image not found: {path}")
            continue
        content.append(load_image(path))
        print(f"  [image loaded: {path}]")
    if text:
        content.append({"type": "text", "text": text})
    return content if content else text


def ask(
    client: anthropic.Anthropic,
    text: str,
    image_paths: list[str],
    conversation: list[dict],
    chapters: dict[str, str],
    index_txt: str,
    titles: list[str],
    skills_content: str,
) -> str:
    """Send a question (with optional images) and stream the response."""
    router_text = text or "analyze this screenshot"
    selected = route_question(client, router_text, index_txt, chapters, titles)
    book_excerpt = "\n\n".join(chapters[t] for t in selected if t in chapters)
    excerpt_tokens = len(book_excerpt) // 4
    print(f"  [router: {selected} — ~{excerpt_tokens:,} tokens]")

    system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT + skills_content,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"## Book Chapters: {', '.join(selected)}\n\n{book_excerpt}",
        },
    ]

    user_content = build_user_content(text, image_paths)
    conversation.append({"role": "user", "content": user_content})

    print("\nAssistant: ", end="", flush=True)
    full_response = []
    try:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=conversation,
        ) as stream:
            for chunk in stream.text_stream:
                print(chunk, end="", flush=True)
                full_response.append(chunk)

        assistant_msg = "".join(full_response)
        conversation.append({"role": "assistant", "content": assistant_msg})

        msg = stream.get_final_message()
        usage = msg.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0)
        cache_create = getattr(usage, "cache_creation_input_tokens", 0)
        print(
            f"\n  [tokens: in={usage.input_tokens} out={usage.output_tokens} "
            f"cache_read={cache_read} cache_create={cache_create}]\n"
        )
        return assistant_msg

    except Exception as e:
        print(f"\nError: {e}\n")
        conversation.pop()
        return ""


def interactive(client, chapters, index_txt, titles, skills_content):
    print("\nAsk me anything about VMware vSphere metrics!")
    print("Prefix image paths with 'image:' on a separate line before your question.")
    print("Type 'reset' to start a new conversation, 'quit' to exit.\n")

    conversation: list[dict] = []

    while True:
        try:
            lines = []
            first = input("You: ").strip()
            if not first:
                continue
            if first.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break
            if first.lower() == "reset":
                conversation.clear()
                print("Conversation reset.\n")
                continue
            lines.append(first)
            # If the first line is an image: prefix, keep reading until a blank line or non-image line
            while first.lower().startswith("image:"):
                try:
                    nxt = input("     ").strip()
                except EOFError:
                    break
                if not nxt:
                    break
                lines.append(nxt)
                first = nxt
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        raw = "\n".join(lines)
        image_paths, text = parse_input(raw)
        if not text and not image_paths:
            continue

        ask(client, text, image_paths, conversation, chapters, index_txt, titles, skills_content)


def main():
    parser = argparse.ArgumentParser(description="VMware vSphere Metrics Q&A CLI")
    parser.add_argument("--question", "-q", help="Question to ask (non-interactive)")
    parser.add_argument("--image", "-i", action="append", default=[], metavar="PATH",
                        help="Image file(s) to include with the question (repeatable)")
    args = parser.parse_args()

    client = anthropic.Anthropic()

    print("Loading chapters...")
    chapters, index_txt, titles = load_chapters()
    total_tokens = sum(len(c) // 4 for c in chapters.values())
    print(f"Loaded {len(chapters)} chapters (~{total_tokens:,} total tokens)")

    skills_content = load_skills()
    skill_names = skill_dirs()
    print(f"Loaded {len(skill_names)} skills: {', '.join(skill_names)}")
    print(f"Model: {MODEL}  |  Router: {ROUTER_MODEL}")

    if args.question or args.image:
        # Non-interactive single-question mode
        conversation: list[dict] = []
        ask(client, args.question or "", args.image, conversation,
            chapters, index_txt, titles, skills_content)
    else:
        interactive(client, chapters, index_txt, titles, skills_content)


if __name__ == "__main__":
    main()
