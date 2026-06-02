"""
API-based evaluation harness for the vSphere Metrics Q&A agent.

Two pieces, both using the Anthropic API (needs ANTHROPIC_API_KEY):
- run_case():       run a question through the real agent pipeline (router + answer),
                    then grade the answer with an LLM judge (Haiku).
- generate_cases(): read a book chapter and have the model produce new test cases in the
                    same schema as book_eval.json ("use the book to generate tests").

Case schema (book_eval.json):
    { "id", "question", "chapter", "expected_points", "must_consider": [...] }
"""
import json
import os

import anthropic

import agent
from qa_common import load_chapters
from skills_loader import load_skills

JUDGE_MODEL = "claude-haiku-4-5-20251001"
GEN_MODEL = "claude-sonnet-4-6"

EVAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "book_eval.json")

JUDGE_PROMPT = """You are grading an answer from a VMware vSphere metrics Q&A assistant.

QUESTION:
{question}

KEY POINTS a correct answer must convey (paraphrase is fine; extra correct detail is fine):
{expected_points}

CANDIDATE ANSWER:
{answer}

Grade PASS only if the candidate answer conveys the key points and does not contradict
them. Grade FAIL if it misses the core idea or states something incorrect.

Respond with ONLY a JSON object: {{"pass": true|false, "reason": "<one sentence>"}}"""

GEN_PROMPT = """You are creating evaluation test cases for a VMware vSphere metrics Q&A
assistant, grounded ONLY in the book chapter provided below.

Produce exactly {n} test cases as a JSON array. Each item must be an object:
  - "id": short kebab-case slug
  - "question": a clear question a vSphere admin would ask, answerable from this chapter
  - "chapter": "{chapter}"
  - "expected_points": 1-3 sentences stating the correct answer / key facts from the chapter
  - "must_consider": array of 1-3 short strings naming the essential points

Make questions varied (definition, comparison, troubleshooting, gotcha). Base every fact
strictly on the chapter text. Respond with ONLY the JSON array.

CHAPTER "{chapter}":
{chapter_text}"""


def _extract_json(text: str):
    """Pull a JSON object/array out of a model reply, tolerating ``` fences and prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    for open_c, close_c in (("[", "]"), ("{", "}")):
        i, j = text.find(open_c), text.rfind(close_c)
        if i != -1 and j != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except Exception:
                continue
    return None


def judge(client: anthropic.Anthropic, question: str, expected_points: str, answer: str) -> tuple[bool, str]:
    """Use Haiku to grade an answer against the expected points. Returns (passed, reason)."""
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": JUDGE_PROMPT.format(
                question=question, expected_points=expected_points, answer=answer
            ),
        }],
    )
    data = _extract_json(resp.content[0].text) or {}
    return bool(data.get("pass")), str(data.get("reason", "no reason returned"))


def run_case(client, case, chapters, index_txt, titles, skills_content) -> dict:
    """Run one eval case end to end: route -> answer -> judge."""
    selected, answer = agent.generate_answer(
        client, case["question"], chapters, index_txt, titles, skills_content
    )
    passed, reason = judge(client, case["question"], case["expected_points"], answer)
    return {
        "id": case["id"],
        "question": case["question"],
        "expected_chapter": case.get("chapter"),
        "selected": selected,
        "answer": answer,
        "passed": passed,
        "reason": reason,
    }


def generate_cases(client, chapter_title: str, chapters: dict, n: int = 4) -> list:
    """Have the model read a chapter and produce n new test cases in the eval schema."""
    if chapter_title not in chapters:
        raise KeyError(f"unknown chapter: {chapter_title!r} (have {list(chapters)})")
    chapter_text = chapters[chapter_title][:120_000]  # keep the request bounded
    resp = client.messages.create(
        model=GEN_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": GEN_PROMPT.format(n=n, chapter=chapter_title, chapter_text=chapter_text),
        }],
    )
    cases = _extract_json(resp.content[0].text) or []
    # keep only well-formed cases
    return [
        c for c in cases
        if isinstance(c, dict) and c.get("question") and c.get("expected_points") and c.get("id")
    ]


def load_cases(path: str = EVAL_PATH) -> list:
    with open(path) as f:
        return json.load(f)


def setup(client=None):
    """Build the (client, chapters, index_txt, titles, skills) tuple used by the harness."""
    client = client or anthropic.Anthropic()
    chapters, index_txt, titles = load_chapters()
    skills_content = load_skills()
    return client, chapters, index_txt, titles, skills_content


if __name__ == "__main__":
    # Ad-hoc run: evaluate every curated case and print a scorecard.
    import sys

    from dotenv import load_dotenv
    load_dotenv()

    client, chapters, index_txt, titles, skills = setup()
    cases = load_cases()
    results = []
    for case in cases:
        r = run_case(client, case, chapters, index_txt, titles, skills)
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['id']:24} routed={r['selected']}  — {r['reason']}")
        results.append(r)
    passed = sum(r["passed"] for r in results)
    print(f"\n{passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)
