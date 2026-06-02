from __future__ import annotations

from typing import List, TypedDict


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
    world_bible: str
    characters: str
    outline: str
    chapter_plan: str
    drafts: List[str]
    critique: str
    continuity_notes: str
    last_chapter_summary: str


class NovelInput(TypedDict, total=False):
    idea: str
    genre: str
    style: str
    mode: str
    source_dir: str
    max_chapters: int
    words_per_chapter: int


def initial_state(
    *,
    idea: str,
    genre: str,
    style: str,
    max_chapters: int,
    words_per_chapter: int,
    mode: str = "new",
    source_dir: str = "",
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
        "world_bible": "",
        "characters": "",
        "outline": "",
        "chapter_plan": "",
        "drafts": [],
        "critique": "",
        "continuity_notes": "",
        "last_chapter_summary": "",
    }


def initial_state_from_input(data: NovelInput) -> NovelState:
    return initial_state(
        idea=data.get("idea") or "穿越恶毒女配嫁入财阀家族后反向改命",
        genre=data.get("genre") or "女频、财阀、穿越、爽文",
        style=data.get("style") or "强情绪、快节奏、反转密集、对白有拉扯",
        mode=data.get("mode") or "new",
        source_dir=data.get("source_dir") or "",
        max_chapters=int(data.get("max_chapters") or 3),
        words_per_chapter=int(data.get("words_per_chapter") or 1800),
    )
