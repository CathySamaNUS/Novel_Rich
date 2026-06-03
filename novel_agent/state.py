from __future__ import annotations

from typing import List, TypedDict


DEFAULT_IDEA = "华裔酒店家族千金回国拓展业务，想避开既定失败线，却卷入财阀圈的合作、暧昧与报复漩涡"
DEFAULT_GENRE = "现言、财阀、豪门修罗场、商业博弈、强情绪"
DEFAULT_STYLE = "快节奏、强情绪、暧昧拉扯、反转明确、章节结尾有钩子"


class NovelState(TypedDict):
    idea: str
    genre: str
    style: str
    mode: str
    source_dir: str
    source_material: str
    existing_chapters_count: int
    generated_chapters_count: int
    max_chapters: int
    words_per_chapter: int
    current_chapter: int
    review_required: bool
    auto_approve: bool
    world_bible: str
    characters: str
    character_state: str
    outline: str
    plot_memory: str
    continuity_notes: str
    last_chapter_summary: str
    current_chapter_plan: str
    current_draft: str
    current_critique: str
    current_review_action: str
    current_human_feedback: str
    current_human_edit: str
    approved_chapter_plans: List[str]
    approved_drafts: List[str]
    approved_critiques: List[str]
    approved_summaries: List[str]


class NovelInput(TypedDict, total=False):
    idea: str
    genre: str
    style: str
    mode: str
    source_dir: str
    max_chapters: int
    words_per_chapter: int
    review_required: bool
    auto_approve: bool


def initial_state(
    *,
    idea: str,
    genre: str,
    style: str,
    max_chapters: int,
    words_per_chapter: int,
    mode: str = "new",
    source_dir: str = "",
    review_required: bool = True,
    auto_approve: bool = False,
) -> NovelState:
    return {
        "idea": idea,
        "genre": genre,
        "style": style,
        "mode": mode,
        "source_dir": source_dir,
        "source_material": "",
        "existing_chapters_count": 0,
        "generated_chapters_count": 0,
        "max_chapters": max_chapters,
        "words_per_chapter": words_per_chapter,
        "current_chapter": 1,
        "review_required": review_required,
        "auto_approve": auto_approve,
        "world_bible": "",
        "characters": "",
        "character_state": "",
        "outline": "",
        "plot_memory": "",
        "continuity_notes": "",
        "last_chapter_summary": "",
        "current_chapter_plan": "",
        "current_draft": "",
        "current_critique": "",
        "current_review_action": "",
        "current_human_feedback": "",
        "current_human_edit": "",
        "approved_chapter_plans": [],
        "approved_drafts": [],
        "approved_critiques": [],
        "approved_summaries": [],
    }


def initial_state_from_input(data: NovelInput) -> NovelState:
    source_dir = (data.get("source_dir") or "").strip()
    mode = data.get("mode") or "new"
    idea = (data.get("idea") or "").strip()
    if not idea:
        idea = source_dir.split("/")[-1] if mode == "continue" and source_dir else DEFAULT_IDEA

    return initial_state(
        idea=idea,
        genre=data.get("genre") or DEFAULT_GENRE,
        style=data.get("style") or DEFAULT_STYLE,
        mode=mode,
        source_dir=source_dir,
        max_chapters=int(data.get("max_chapters") or 3),
        words_per_chapter=int(data.get("words_per_chapter") or 1800),
        review_required=bool(data.get("review_required", True)),
        auto_approve=bool(data.get("auto_approve", False)),
    )
