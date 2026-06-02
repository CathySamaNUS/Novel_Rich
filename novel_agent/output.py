from __future__ import annotations

import re
from pathlib import Path

from .state import NovelState


def write_project(state: NovelState, root: Path) -> Path:
    project_dir = root / slugify(state["idea"])
    chapters_dir = project_dir / "chapters"
    reviews_dir = project_dir / "reviews"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "world_bible.md").write_text(state["world_bible"], encoding="utf-8")
    (project_dir / "characters.md").write_text(state["characters"], encoding="utf-8")
    (project_dir / "outline.md").write_text(state["outline"], encoding="utf-8")
    (project_dir / "continuity_notes.md").write_text(
        state["continuity_notes"], encoding="utf-8"
    )
    (reviews_dir / "latest_critique.md").write_text(state["critique"], encoding="utf-8")

    full = []
    for index, draft in enumerate(state["drafts"], start=1):
        chapter_name = f"{index:02d}-chapter.md"
        (chapters_dir / chapter_name).write_text(draft, encoding="utf-8")
        full.append(f"# 第{index}章\n\n{draft}")

    (project_dir / "full_draft.md").write_text("\n\n".join(full), encoding="utf-8")
    return project_dir


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value)
    value = value.strip("-")
    return value[:80] or "novel"

