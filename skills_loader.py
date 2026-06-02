"""
Agent Skills loader.

Skills live in `skills/<name>/SKILL.md` (Agent Skills format): a YAML frontmatter
block with `name` and `description`, followed by the skill body. This module reads
them and builds the `## Skills` section that is appended to the system prompt.

Kept dependency-free (stdlib only) so it can be imported and unit-tested without the
anthropic / fastapi stack.
"""
import os

SKILLS_HEADER = (
    "\n## Skills\n\nYou have specialized skills that can be activated. "
    "When activated, follow the skill instructions precisely.\n\n"
)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a leading YAML frontmatter block (--- ... ---) from the body.

    Returns (meta, body). Minimal parser: handles `key: value` lines only, which is
    all the Agent Skills frontmatter needs (name, description). If there is no
    frontmatter, returns ({}, text) unchanged.
    """
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            meta: dict = {}
            for line in text[3:end].strip("\n").splitlines():
                if ":" in line:
                    key, _, value = line.partition(":")
                    meta[key.strip()] = value.strip()
            return meta, text[end + 4:].lstrip("\n")
    return {}, text


def skill_dirs(skills_dir: str = "skills") -> list[str]:
    """Return skill names (subdirectories containing a SKILL.md), sorted."""
    if not os.path.isdir(skills_dir):
        return []
    return sorted(
        d for d in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, d, "SKILL.md"))
    )


def load_skill(skills_dir: str, name: str) -> tuple[dict, str]:
    """Read one skill, returning (meta, body)."""
    with open(os.path.join(skills_dir, name, "SKILL.md")) as f:
        return parse_frontmatter(f.read())


def load_skills(skills_dir: str = "skills") -> str:
    """Load all Agent Skills and concatenate their bodies into a prompt section."""
    if not os.path.isdir(skills_dir):
        return ""
    text = SKILLS_HEADER
    for name in skill_dirs(skills_dir):
        _meta, body = load_skill(skills_dir, name)
        text += body.rstrip() + "\n\n"
    return text
