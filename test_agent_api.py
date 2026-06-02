"""
API-based integration tests: run book-grounded questions through the real agent pipeline
(router + answer via the Anthropic API) and grade each answer with an LLM judge.

These cost tokens, so they are SKIPPED unless you opt in:
    RUN_API_TESTS=1 ANTHROPIC_API_KEY=sk-... pytest test_agent_api.py -v
    # or, using the project venv:
    RUN_API_TESTS=1 .venv/bin/python -m pytest test_agent_api.py -v

Without RUN_API_TESTS=1 (or without a key) every test is skipped, so the default
`pytest` run stays fast, offline, and free.
"""
import os

import pytest

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

RUN = os.environ.get("RUN_API_TESTS") == "1" and bool(os.environ.get("ANTHROPIC_API_KEY"))

pytestmark = pytest.mark.skipif(
    not RUN,
    reason="set RUN_API_TESTS=1 and ANTHROPIC_API_KEY to run live API eval tests",
)

# Imported lazily-safe: eval_harness imports anthropic, which is only needed when RUN.
if RUN:
    import eval_harness


@pytest.fixture(scope="module")
def harness():
    return eval_harness.setup()


@pytest.fixture(scope="module")
def cases():
    return eval_harness.load_cases()


def _ids(cases):
    return [c["id"] for c in cases]


# One test per curated case (parametrized by id), so failures point at the exact question.
CURATED = eval_harness.load_cases() if RUN else []


@pytest.mark.parametrize("case", CURATED, ids=_ids(CURATED))
def test_curated_case_answer_is_correct(case, harness):
    client, chapters, index_txt, titles, skills = harness
    result = eval_harness.run_case(client, case, chapters, index_txt, titles, skills)
    assert result["passed"], (
        f"{case['id']}: judge FAILED — {result['reason']}\n"
        f"routed={result['selected']}\nanswer:\n{result['answer'][:800]}"
    )


@pytest.mark.parametrize("case", CURATED, ids=_ids(CURATED))
def test_router_is_well_formed(case, harness):
    """Routing invariants (deterministic): non-empty, a subset of real chapters, and always
    includes Introduction. The expected chapter is only a soft signal — which resource
    chapter best answers a question is a judgment call, so we don't hard-assert it here
    (the answer-correctness tests already exercise that the right content was routed)."""
    client, chapters, index_txt, titles, skills = harness
    selected = __import__("agent").route_question(
        client, case["question"], index_txt, chapters, titles
    )
    assert selected, f"{case['id']}: router returned no chapters"
    assert set(selected) <= set(titles), f"{case['id']}: router returned unknown chapters: {selected}"
    assert "Introduction" in selected, f"{case['id']}: Introduction should always be included, got {selected}"


def test_generated_cases_from_book_pass(harness):
    """Use the book to generate fresh test cases, then the agent must pass its own book quiz."""
    client, chapters, index_txt, titles, skills = harness
    generated = eval_harness.generate_cases(client, "CPU", chapters, n=3)
    assert generated, "generator produced no usable cases"
    results = [
        eval_harness.run_case(client, c, chapters, index_txt, titles, skills)
        for c in generated
    ]
    passed = sum(r["passed"] for r in results)
    # Allow one miss on auto-generated questions (they can be ambiguous).
    assert passed >= len(results) - 1, (
        "too many generated cases failed:\n"
        + "\n".join(f"  [{'PASS' if r['passed'] else 'FAIL'}] {r['id']}: {r['reason']}" for r in results)
    )
