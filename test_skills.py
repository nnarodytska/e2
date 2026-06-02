"""
Tests for the Agent Skills loader (skills_loader.py) and the skills/ directory.

Run with either:
    pytest test_skills.py
    python3 test_skills.py

These are dependency-free (no anthropic/fastapi needed) so they validate the skill
format and loader in isolation.
"""
import os
import re

import skills_loader

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(HERE, "skills")

# Every skill we expect to ship, by directory name (kebab-case == frontmatter name).
EXPECTED_SKILLS = {
    "compare",
    "cpu-frequency",
    "esxi-capacity",
    "explore",
    "formatting",
    "guest-os-cpu",
    "performance-vs-capacity",
    "troubleshoot",
    "troubleshoot-cpu",
    "troubleshoot-memory",
    "vm-rightsize",
}

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# --- parse_frontmatter ------------------------------------------------------

def test_parse_frontmatter_extracts_keys_and_strips_block():
    text = "---\nname: demo\ndescription: A demo skill.\n---\n\n# Body\nhello\n"
    meta, body = skills_loader.parse_frontmatter(text)
    assert meta == {"name": "demo", "description": "A demo skill."}
    assert body == "# Body\nhello\n"
    assert "---" not in body


def test_parse_frontmatter_no_frontmatter_is_passthrough():
    text = "# Just a body\nno frontmatter here\n"
    meta, body = skills_loader.parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_description_with_colons_preserved():
    text = "---\nname: x\ndescription: Use when: A vs B; X versus Y.\n---\nbody\n"
    meta, body = skills_loader.parse_frontmatter(text)
    assert meta["description"] == "Use when: A vs B; X versus Y."
    assert body == "body\n"


# --- skill_dirs -------------------------------------------------------------

def test_skill_dirs_finds_exactly_expected_skills():
    assert set(skills_loader.skill_dirs(SKILLS_DIR)) == EXPECTED_SKILLS


def test_skill_dirs_is_sorted():
    names = skills_loader.skill_dirs(SKILLS_DIR)
    assert names == sorted(names)


def test_skill_dirs_missing_dir_returns_empty():
    assert skills_loader.skill_dirs(os.path.join(HERE, "does-not-exist")) == []


# --- the skill files themselves ---------------------------------------------

def test_every_skill_has_valid_frontmatter():
    for name in skills_loader.skill_dirs(SKILLS_DIR):
        meta, body = skills_loader.load_skill(SKILLS_DIR, name)
        assert meta.get("name") == name, f"{name}: frontmatter name must match dir"
        assert KEBAB.match(name), f"{name}: dir name must be kebab-case"
        assert meta.get("description"), f"{name}: missing description"
        assert len(meta["description"]) <= 1024, f"{name}: description too long"
        assert body.strip(), f"{name}: empty body"


# --- load_skills ------------------------------------------------------------

def test_load_skills_includes_header_and_all_bodies():
    text = skills_loader.load_skills(SKILLS_DIR)
    assert "## Skills" in text
    # A distinctive phrase from a couple of skill bodies should survive.
    assert "Answer Formatting" in text
    assert "Right-Sizing" in text


def test_load_skills_strips_all_frontmatter():
    text = skills_loader.load_skills(SKILLS_DIR)
    # No leftover frontmatter delimiters or keys should leak into the prompt.
    assert "\n---\nname:" not in text
    assert "description:" not in text


def test_load_skills_missing_dir_returns_empty():
    assert skills_loader.load_skills(os.path.join(HERE, "does-not-exist")) == ""


if __name__ == "__main__":
    # Minimal runner so the suite works without pytest installed.
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
