# VMware vSphere Metrics Q&A Agent

A Q&A agent that answers questions about VMware vSphere metrics using the full "VMware vSphere Metrics" book as its knowledge base. Runs as a FastAPI web app or a terminal CLI, with two interchangeable backends: the **Anthropic API** (needs an API key) or the **`claude` CLI** (no API key — uses your Claude login).

## Architecture

```
User question
     |
     v
Router (Haiku) ──> selects relevant chapters (~2K tokens)
     |
     v
Answer (Sonnet) ──> responds using selected chapters + 11 skills (~30-60K tokens)
     |               via the Anthropic API  OR  the `claude` CLI
     v
Streamed response with feedback collection
```

- **Two backends** — Anthropic API (`app.py`, `agent.py`) or the `claude` CLI with no API key (`agent_claude.py`)
- **Dynamic chapter routing** — only loads relevant chapters instead of the full book
- **Prompt caching** — system prompt and skills are cached across questions (API backend)
- **Auto-triggered skills** — 11 skills in Agent Skills format (formatting, troubleshooting, comparison, capacity, right-sizing, …)
- **Image upload** — users can paste/upload vSphere screenshots for analysis (web app)
- **Feedback collection** — thumbs up/down with optional comments stored in SQLite

## Prerequisites

- Python 3.12+
- **Either** an Anthropic API key (for `app.py` / `agent.py`) **or** the [`claude` CLI](https://claude.com/claude-code) logged in (for `agent_claude.py` — no API key needed)

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/nnarodytska/e2.git
cd e2
pip install -r requirements.txt
```

### 2. Set up environment

Only needed for the API-key backends (`app.py`, `agent.py`). **Skip this if you'll use
`agent_claude.py`** — it authenticates through the `claude` CLI instead.

Create a `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Run

**Web app:**
```bash
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```
Open http://localhost:8000

**CLI (terminal chat):**
```bash
python3 agent.py
```

**CLI without an API key (uses the `claude` command line):**
```bash
python3 agent_claude.py                              # interactive
python3 agent_claude.py -q "What is CPU Ready?"      # single question
python3 agent_claude.py -q "..." --no-route          # send the whole book (skip routing)
```
This variant needs **no `ANTHROPIC_API_KEY`**. Instead it shells out to the `claude` CLI
(Claude Code), reusing whatever login that command is authenticated with (e.g. a Claude
subscription). Make sure `claude` is installed and logged in first:

```bash
claude auth login        # one-time browser sign-in
claude auth status       # should show "loggedIn": true
```

Same architecture as `agent.py` (Haiku router → Sonnet answer with the selected chapters +
skills), just a different backend. Internally it passes the book context via a temporary
`--system-prompt-file` and the question over stdin.

> Each question is answered independently (no multi-turn memory), since every question
> re-routes to a fresh set of book chapters.

## Project Structure

```
├── app.py                  # Web app (FastAPI + chat UI)          [Anthropic API]
├── agent.py                # CLI agent (interactive terminal)     [Anthropic API]
├── agent_claude.py         # CLI agent via the `claude` command    [no API key]
├── claude_backend.py       # Wrapper around the `claude` CLI
├── qa_common.py            # Shared prompts, chapter loading, routing-reply parsing
├── skills_loader.py        # Loads skills/<name>/SKILL.md into the system prompt
├── test_*.py               # Tests (skills loader, qa_common, claude backend)
├── requirements.txt        # Python dependencies
├── .env                    # API key (only needed for app.py / agent.py)
│
├── book.md                 # Full book markdown (with image descriptions)
│
├── chapters/               # Book split into individual chapters
│   ├── chapter_index.json  # Chapter metadata and sections
│   ├── chapter_index.txt   # Compact index for router prompt
│   ├── 00_preamble.md
│   ├── 01_introduction.md
│   ├── 02_cpu.md
│   └── ...
│
├── skills/                 # Auto-triggered agent skills (Agent Skills format)
│   ├── formatting/SKILL.md     # Answer structure (always active)
│   ├── troubleshoot/SKILL.md   # Troubleshooting decision trees
│   ├── compare/SKILL.md        # Side-by-side metric comparison
│   └── .../SKILL.md
│
└── feedback.db             # Conversations + feedback (SQLite, auto-created)
```

## Skills

Skills follow the **Agent Skills format**: each is a directory `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) followed by the skill body. They are loaded automatically at startup and appended to the system prompt — no code changes needed.

```markdown
---
name: troubleshoot-cpu
description: Use when the user reports VM CPU contention (slow VM, high CPU Ready, ...).
---

### Skill: CPU Performance Troubleshooting Wizard
...
```

| Skill | Directory | Trigger |
|-------|-----------|---------|
| **Formatting** | `formatting/` | Always active. Structures every answer with TL;DR, Details, Action, Book ref. |
| **Troubleshoot** | `troubleshoot/` | When user describes a performance problem. |
| **Troubleshoot CPU** | `troubleshoot-cpu/` | When user reports VM CPU contention (high Ready, co-stop, slow VM). |
| **Troubleshoot Memory** | `troubleshoot-memory/` | When user reports VM memory contention (balloon, swap, latency). |
| **CPU Frequency** | `cpu-frequency/` | When user asks about actual CPU speed, Turbo Boost, or power policy effects. |
| **Compare** | `compare/` | When user asks about differences between metrics ("X vs Y"). |
| **Explore** | `explore/` | When user asks about a specific metric across levels (VM/ESXi/Cluster). |
| **ESXi Capacity** | `esxi-capacity/` | When the question is about ESXi host CPU capacity / "true utilization". |
| **Guest OS CPU** | `guest-os-cpu/` | When the question is about Guest OS CPU awareness (run queue, HT). |
| **Performance vs Capacity** | `performance-vs-capacity/` | When comparing performance vs capacity management. |
| **VM Right-Sizing** | `vm-rightsize/` | When the question is about VM CPU right-sizing metrics. |

To add a new skill, create `skills/<name>/SKILL.md` with frontmatter and restart the server.

### Testing

**Offline tests** (no API key, fast, free) — the default:

```bash
pytest                       # runs all offline tests; API tests auto-skip
# or run a file directly without pytest:
python3 test_skills.py
python3 test_qa_common.py
python3 test_claude_backend.py
```

- `test_skills.py` — loader + every skill's frontmatter (name matches directory, kebab-case, non-empty description).
- `test_qa_common.py` — chapter loading, input parsing, and router-reply parsing.
- `test_claude_backend.py` — `claude` CLI argv construction and the missing-CLI error path (does not invoke the CLI).

**API eval tests** (live, book-grounded — needs an API key, costs tokens):

```bash
RUN_API_TESTS=1 ANTHROPIC_API_KEY=sk-... pytest test_agent_api.py -v
```

These run book-grounded questions through the **real** pipeline (router → answer) and grade
each answer with an LLM judge (Haiku). Cases live in `book_eval.json`; one test also uses the
book to **generate fresh cases** and checks the agent passes its own quiz. Without
`RUN_API_TESTS=1` they skip, so the default `pytest` stays offline.

Generate more cases from the book and inspect a scorecard:

```bash
python3 gen_book_eval.py --chapter CPU --chapter Memory -n 4 -o book_eval_generated.json
python3 eval_harness.py        # evaluate every case in book_eval.json, print PASS/FAIL
```

## Costs

**`claude` CLI backend (`agent_claude.py`):** no per-token API charge — it uses your
Claude subscription, subject to that plan's usage limits.

**Anthropic API backend (`app.py`, `agent.py`):** billed per token. The system+skills
prompt (~5K tokens) is cached after the first question. Book chapters are selected
dynamically per question and are not cached.

| Scenario | Tokens | Cost per question |
|----------|--------|-------------------|
| First question (cache write for skills) | ~5K skills + ~20–50K chapters | ~$0.08–$0.20 |
| Subsequent questions (skills cached) | ~5K cached + ~20–50K chapters | ~$0.06–$0.18 |
| Router call (Haiku) | ~2K | ~$0.001 |
| 10-question session | | ~$0.70–$1.80 |

## Viewing Feedback

```bash
# All feedback
sqlite3 feedback.db "SELECT created_at, rating, comment, substr(question,1,60) FROM feedback ORDER BY created_at DESC"

# Thumbs down with comments
sqlite3 feedback.db "SELECT created_at, comment, substr(question,1,60) FROM feedback WHERE rating='down' AND comment != '' ORDER BY created_at DESC"
```

Or visit `/conversations` in the web app for a full admin view with ratings.
