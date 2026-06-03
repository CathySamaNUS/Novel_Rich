from __future__ import annotations

import re
from pathlib import Path

from .state import NovelState


def write_project(state: NovelState, root: Path) -> Path:
    project_dir = root / slugify(state["idea"])
    chapters_dir = project_dir / "chapters"
    reviews_dir = project_dir / "reviews"
    plans_dir = project_dir / "plans"
    summaries_dir = project_dir / "summaries"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    reviews_dir.mkdir(parents=True, exist_ok=True)
    plans_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)

    (project_dir / "world_bible.md").write_text(state["world_bible"], encoding="utf-8")
    (project_dir / "characters.md").write_text(state["characters"], encoding="utf-8")
    (project_dir / "character_state.md").write_text(
        state["character_state"], encoding="utf-8"
    )
    (project_dir / "outline.md").write_text(state["outline"], encoding="utf-8")
    (project_dir / "plot_memory.md").write_text(state["plot_memory"], encoding="utf-8")
    (project_dir / "continuity_notes.md").write_text(
        state["continuity_notes"], encoding="utf-8"
    )
    (project_dir / "last_chapter_summary.md").write_text(
        state["last_chapter_summary"], encoding="utf-8"
    )

    latest_critique = state["current_critique"] or (
        state["approved_critiques"][-1] if state["approved_critiques"] else ""
    )
    (reviews_dir / "latest_critique.md").write_text(latest_critique, encoding="utf-8")

    full = []
    start_index = state["existing_chapters_count"] + 1
    for offset, draft in enumerate(state["approved_drafts"]):
        chapter_number = start_index + offset
        chapter_name = f"{chapter_number:02d}-chapter.md"
        (chapters_dir / chapter_name).write_text(draft, encoding="utf-8")
        full.append(f"# 第{chapter_number}章\n\n{draft}")

    for offset, plan in enumerate(state["approved_chapter_plans"]):
        chapter_number = start_index + offset
        (plans_dir / f"{chapter_number:02d}-plan.md").write_text(plan, encoding="utf-8")

    for offset, critique in enumerate(state["approved_critiques"]):
        chapter_number = start_index + offset
        (reviews_dir / f"{chapter_number:02d}-critique.md").write_text(
            critique, encoding="utf-8"
        )

    for offset, summary in enumerate(state["approved_summaries"]):
        chapter_number = start_index + offset
        (summaries_dir / f"{chapter_number:02d}-summary.md").write_text(
            summary, encoding="utf-8"
        )

    (project_dir / "full_draft.md").write_text("\n\n".join(full), encoding="utf-8")
    return project_dir


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value)
    value = value.strip("-")
    return value[:80] or "novel"
