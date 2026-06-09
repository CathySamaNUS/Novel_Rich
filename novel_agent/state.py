from __future__ import annotations

from typing import List, TypedDict

from .writing_skill import DEFAULT_NOVEL_SKILL, DEFAULT_SHARED_SKILL


DEFAULT_IDEA = "华裔酒店家族千金回国拓展业务，想避开既定失败线，却卷入财阀圈的合作、暧昧与报复漩涡"
DEFAULT_GENRE = "现言、财阀、豪门修罗场、商业博弈、强情绪"
DEFAULT_STYLE = "快节奏、强情绪、暧昧拉扯、反转明确、章节结尾有钩子"
DEFAULT_SKILL_EVOLUTION_WINDOW = 2
DEFAULT_SKILL_FAILURE_THRESHOLD = 2


class NovelState(TypedDict):
    idea: str
    genre: str
    style: str
    mode: str
    source_dir: str
    output_dir: str
    source_material: str
    existing_chapters_count: int
    generated_chapters_count: int
    max_chapters: int
    words_per_chapter: int
    current_chapter: int
    review_required: bool
    auto_approve: bool
    world_bible: str
    enable_writing_skill: bool
    enable_skill_evolution: bool
    enable_memory_evolution: bool
    skill_evolution_window: int
    skill_failure_threshold: int
    shared_writing_skill: str
    novel_writing_skill: str
    characters: str
    character_state: str
    outline: str
    plot_memory: str
    continuity_notes: str
    last_chapter_summary: str
    current_chapter_plan: str
    current_draft: str
    current_critique: str
    current_regenerate_brief: str
    current_review_action: str
    current_human_feedback: str
    current_human_edit: str
    current_chapter_had_failure: bool
    current_chapter_feedback_log: str
    current_skill_update_suggestion: str
    current_skill_review_action: str
    current_skill_edit: str
    current_memory_update_suggestion: str
    current_memory_review_action: str
    current_memory_edit: str
    force_memory_flag: bool
    recent_critiques: List[str]
    recent_human_feedback: List[str]
    recent_failure_flags: List[bool]
    approved_chapter_plans: List[str]
    approved_drafts: List[str]
    approved_critiques: List[str]
    approved_summaries: List[str]
    approved_skill_updates: List[str]
    approved_memory_updates: List[str]


class NovelInput(TypedDict, total=False):
    idea: str
    genre: str
    style: str
    mode: str
    source_dir: str
    output_dir: str
    enable_writing_skill: bool
    enable_skill_evolution: bool
    enable_memory_evolution: bool
    skill_evolution_window: int
    skill_failure_threshold: int
    shared_writing_skill: str
    novel_writing_skill: str
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
    output_dir: str = "output",
    enable_writing_skill: bool = False,
    enable_skill_evolution: bool = False,
    enable_memory_evolution: bool = False,
    skill_evolution_window: int = DEFAULT_SKILL_EVOLUTION_WINDOW,
    skill_failure_threshold: int = DEFAULT_SKILL_FAILURE_THRESHOLD,
    review_required: bool = True,
    auto_approve: bool = False,
) -> NovelState:
    return {
        "idea": idea,
        "genre": genre,
        "style": style,
        "mode": mode,
        "source_dir": source_dir,
        "output_dir": output_dir or "output",
        "source_material": "",
        "existing_chapters_count": 0,
        "generated_chapters_count": 0,
        "max_chapters": max_chapters,
        "words_per_chapter": words_per_chapter,
        "current_chapter": 1,
        "review_required": review_required,
        "auto_approve": auto_approve,
        "world_bible": "",
        "enable_writing_skill": enable_writing_skill,
        "enable_skill_evolution": enable_skill_evolution,
        "enable_memory_evolution": enable_memory_evolution,
        "skill_evolution_window": max(1, skill_evolution_window),
        "skill_failure_threshold": max(1, skill_failure_threshold),
        "shared_writing_skill": DEFAULT_SHARED_SKILL if enable_writing_skill else "",
        "novel_writing_skill": DEFAULT_NOVEL_SKILL if enable_writing_skill else "",
        "characters": "",
        "character_state": "",
        "outline": "",
        "plot_memory": "",
        "continuity_notes": "",
        "last_chapter_summary": "",
        "current_chapter_plan": "",
        "current_draft": "",
        "current_critique": "",
        "current_regenerate_brief": "",
        "current_review_action": "",
        "current_human_feedback": "",
        "current_human_edit": "",
        "current_chapter_had_failure": False,
        "current_chapter_feedback_log": "",
        "current_skill_update_suggestion": "",
        "current_skill_review_action": "",
        "current_skill_edit": "",
        "current_memory_update_suggestion": "",
        "current_memory_review_action": "",
        "current_memory_edit": "",
        "force_memory_flag": False,
        "recent_critiques": [],
        "recent_human_feedback": [],
        "recent_failure_flags": [],
        "approved_chapter_plans": [],
        "approved_drafts": [],
        "approved_critiques": [],
        "approved_summaries": [],
        "approved_skill_updates": [],
        "approved_memory_updates": [],
    }


def initial_state_from_input(data: NovelInput) -> NovelState:
    source_dir = (data.get("source_dir") or "").strip()
    output_dir = (data.get("output_dir") or "").strip() or "output"
    mode = data.get("mode") or "new"
    idea = (data.get("idea") or "").strip()
    if not idea:
        idea = source_dir.split("/")[-1] if mode == "continue" and source_dir else DEFAULT_IDEA

    enable_skill_evolution = bool(data.get("enable_skill_evolution", False))
    enable_writing_skill = bool(data.get("enable_writing_skill", False) or enable_skill_evolution)
    # 默认：开启 skill_evolution 时同时开启 memory_evolution；用户可显式覆盖
    enable_memory_evolution = bool(
        data.get("enable_memory_evolution", enable_skill_evolution)
    )

    state = initial_state(
        idea=idea,
        genre=data.get("genre") or DEFAULT_GENRE,
        style=data.get("style") or DEFAULT_STYLE,
        mode=mode,
        source_dir=source_dir,
        output_dir=output_dir,
        enable_writing_skill=enable_writing_skill,
        enable_skill_evolution=enable_skill_evolution,
        enable_memory_evolution=enable_memory_evolution,
        skill_evolution_window=int(
            data.get("skill_evolution_window") or DEFAULT_SKILL_EVOLUTION_WINDOW
        ),
        skill_failure_threshold=int(
            data.get("skill_failure_threshold") or DEFAULT_SKILL_FAILURE_THRESHOLD
        ),
        max_chapters=int(data.get("max_chapters") or 3),
        words_per_chapter=int(data.get("words_per_chapter") or 1800),
        review_required=bool(data.get("review_required", True)),
        auto_approve=bool(data.get("auto_approve", False)),
    )

    shared_skill = (data.get("shared_writing_skill") or "").strip()
    novel_skill = (data.get("novel_writing_skill") or "").strip()
    if state["enable_writing_skill"] and shared_skill:
        state["shared_writing_skill"] = shared_skill
    if state["enable_writing_skill"] and novel_skill:
        state["novel_writing_skill"] = novel_skill
    return state
