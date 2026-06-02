"""
Shared, dependency-free pieces of the vSphere Metrics Q&A agent.

Both backends import from here:
- agent.py          -> Anthropic API (needs ANTHROPIC_API_KEY)
- agent_claude.py   -> claude CLI (needs no API key, uses your Claude login)

Stdlib only, so it can be imported and unit-tested without anthropic/fastapi.
"""
import json
import os
import sys

CHAPTERS_DIR = "chapters"
CHAPTERS_INDEX = os.path.join(CHAPTERS_DIR, "chapter_index.json")
CHAPTERS_INDEX_TXT = os.path.join(CHAPTERS_DIR, "chapter_index.txt")
SKILLS_DIR = "skills"

SYSTEM_PROMPT = """You are an expert VMware vSphere metrics advisor. You have deep knowledge of VMware vSphere metrics from the authoritative book "VMware vSphere Metrics" which is provided in full below.

## How to answer questions

1. **Use the book as your primary source.** Always ground your answers in the book's content. If the book covers a topic, use its reasoning and explanations rather than general knowledge.

2. **Preserve reasoning chains.** The book explains WHY metrics behave certain ways — the architecture behind them. When answering, include this reasoning so users truly understand, not just memorize.

3. **Cite sections.** Reference the relevant chapter and section (e.g., "As explained in CPU > VM > Contention Metrics > Ready") so users can look up the full context.

4. **Be precise about metric distinctions.** The book emphasizes that:
   - Same-named metrics can have different formulas across different objects (VM vs ESXi vs Cluster)
   - Metrics that sound similar may measure fundamentally different things
   - Context (VM level vs vCPU level vs ESXi level) changes the meaning
   Always clarify these distinctions.

5. **Use the Triple See Method** when it helps structure an answer: see Contention (something bad — performance/availability), Consumption (something good — capacity/cost), and Context (the "it depends" factor — configuration/inventory) together as one integrated set before concluding.

6. **Handle ambiguity.** If a question could refer to metrics at different levels (VM, ESXi, Cluster), ask for clarification or explain the differences at each level.

7. **Be honest about gaps.** If the book doesn't cover something (e.g., it notes vSAN and NSX metrics are not yet added), say so clearly.
"""

ROUTER_PROMPT = """You are a router for a VMware vSphere metrics Q&A system. Given a user question, select which book chapters are needed to answer it.

Available chapters:
{chapter_index}

Rules:
- Always include "Introduction" — it has foundational concepts needed for all answers.
- Select 1-3 additional chapters that are most relevant to the question.
- If unsure, include more chapters rather than fewer.
- For troubleshooting questions, include the relevant resource chapter (CPU, Memory, Storage, Network) AND "Provider" (which covers cluster-level and ESXi-level views).
- For capacity planning, include "Consumer" and/or "Provider".
- For Windows guest OS questions, include "MS Windows".

Respond with ONLY a JSON array of chapter titles. Example: ["Introduction", "CPU", "Provider"]"""


def load_chapters(chapters_dir: str = CHAPTERS_DIR) -> tuple[dict, str, list]:
    """Load the chapter index and all chapter content. Returns (chapters, index_txt, titles)."""
    index_path = os.path.join(chapters_dir, "chapter_index.json")
    index_txt_path = os.path.join(chapters_dir, "chapter_index.txt")
    if not os.path.exists(index_path):
        print(f"Error: {index_path} not found. Run preprocess.py first.")
        sys.exit(1)

    with open(index_path) as f:
        index = json.load(f)
    with open(index_txt_path) as f:
        index_txt = f.read()

    chapters: dict = {}
    titles: list = []
    for entry in index:
        with open(os.path.join(chapters_dir, entry["filename"])) as f:
            chapters[entry["title"]] = f.read()
        titles.append(entry["title"])

    return chapters, index_txt, titles


def parse_chapter_selection(text: str, chapters: dict, titles: list) -> list:
    """Parse a router reply (a JSON array of chapter titles) into a validated list.

    Tolerates ```-fenced JSON. Always ensures "Introduction" is present. Falls back to
    all titles if the reply can't be parsed or yields nothing valid.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        selected = json.loads(text)
    except Exception:
        return titles
    if not isinstance(selected, list):
        return titles
    valid = [t for t in selected if t in chapters]
    if "Introduction" not in valid and "Introduction" in chapters:
        valid.insert(0, "Introduction")
    return valid if valid else titles


def build_book_excerpt(selected: list, chapters: dict) -> str:
    """Concatenate the selected chapters' text."""
    return "\n\n".join(chapters[t] for t in selected if t in chapters)


def parse_input(raw: str) -> tuple[list, str]:
    """Parse raw multi-line input into (image_paths, text).

    Lines starting with 'image:' (case-insensitive) are treated as image paths.
    All other lines form the text message.
    """
    image_paths = []
    text_lines = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("image:"):
            path = stripped[6:].strip()
            if path:
                image_paths.append(path)
        else:
            text_lines.append(stripped)
    return image_paths, "\n".join(l for l in text_lines if l).strip()
