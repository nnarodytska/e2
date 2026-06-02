"""
Tests for qa_common.py (shared prompts, chapter loading, routing-reply parsing).

Run with: pytest test_qa_common.py   or   python3 test_qa_common.py
Dependency-free (no anthropic / claude CLI needed).
"""
import os

import qa_common

HERE = os.path.dirname(os.path.abspath(__file__))
CHAPTERS_DIR = os.path.join(HERE, "chapters")

FAKE_CHAPTERS = {"Introduction": "intro text", "CPU": "cpu text", "Memory": "mem text"}
FAKE_TITLES = list(FAKE_CHAPTERS)


# --- load_chapters ----------------------------------------------------------

def test_load_chapters_returns_titles_and_content():
    chapters, index_txt, titles = qa_common.load_chapters(CHAPTERS_DIR)
    assert "Introduction" in titles
    assert len(chapters) == len(titles) >= 5
    assert all(chapters[t].strip() for t in titles)
    assert index_txt.strip()


# --- parse_input ------------------------------------------------------------

def test_parse_input_separates_images_and_text():
    images, text = qa_common.parse_input("image: /a/b.png\nWhat is shown here?")
    assert images == ["/a/b.png"]
    assert text == "What is shown here?"


def test_parse_input_text_only():
    images, text = qa_common.parse_input("Just a question")
    assert images == []
    assert text == "Just a question"


def test_parse_input_multiple_images_case_insensitive():
    images, text = qa_common.parse_input("IMAGE: x.png\nimage: y.jpg\nhello")
    assert images == ["x.png", "y.jpg"]
    assert text == "hello"


# --- parse_chapter_selection ------------------------------------------------

def test_parse_chapter_selection_valid_json():
    out = qa_common.parse_chapter_selection('["Introduction", "CPU"]', FAKE_CHAPTERS, FAKE_TITLES)
    assert out == ["Introduction", "CPU"]


def test_parse_chapter_selection_code_fenced():
    reply = '```json\n["CPU"]\n```'
    out = qa_common.parse_chapter_selection(reply, FAKE_CHAPTERS, FAKE_TITLES)
    # Introduction is always force-included, prepended.
    assert out == ["Introduction", "CPU"]


def test_parse_chapter_selection_filters_unknown_chapters():
    out = qa_common.parse_chapter_selection('["CPU", "Nonsense"]', FAKE_CHAPTERS, FAKE_TITLES)
    assert "Nonsense" not in out
    assert "CPU" in out


def test_parse_chapter_selection_invalid_json_falls_back_to_all():
    out = qa_common.parse_chapter_selection("not json at all", FAKE_CHAPTERS, FAKE_TITLES)
    assert out == FAKE_TITLES


def test_parse_chapter_selection_non_list_falls_back_to_all():
    out = qa_common.parse_chapter_selection('{"a": 1}', FAKE_CHAPTERS, FAKE_TITLES)
    assert out == FAKE_TITLES


# --- build_book_excerpt -----------------------------------------------------

def test_build_book_excerpt_concatenates_selected_only():
    excerpt = qa_common.build_book_excerpt(["Introduction", "CPU"], FAKE_CHAPTERS)
    assert "intro text" in excerpt
    assert "cpu text" in excerpt
    assert "mem text" not in excerpt


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
