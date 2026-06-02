from __future__ import annotations

import re
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from .prompts import (
    chapter_plan_prompt,
    character_prompt,
    critique_prompt,
    draft_prompt,
    outline_prompt,
    revise_prompt,
    summarize_prompt,
    world_prompt,
)
from .state import NovelInput, NovelState, initial_state_from_input

DEFAULT_SOURCE_DIR = (
    "/Users/cathy/Documents/Novel/穿越女配财阀/novel/狗血财阀文"
)


def build_graph(model, *, studio_input: bool = False):
    def call(prompt: str) -> str:
        return model.invoke(prompt).content

    def build_world(state: NovelState):
        return {"world_bible": call(world_prompt(state))}

    def build_characters(state: NovelState):
        return {"characters": call(character_prompt(state))}

    def build_outline(state: NovelState):
        return {"outline": call(outline_prompt(state))}

    def load_source_material(state: NovelState):
        if state.get("mode") != "continue":
            return {}

        source_dir = Path(state.get("source_dir") or DEFAULT_SOURCE_DIR).expanduser()
        if not source_dir.exists():
            raise FileNotFoundError(f"source_dir not found: {source_dir}")

        characters = _read_optional(source_dir / "人物设定.md")
        summary = _read_optional(source_dir / "SUMMARY.md")
        chapters_dir = source_dir / "chapters"
        chapter_files = sorted(
            chapters_dir.glob("*.md"),
            key=lambda path: (_chapter_number(path), path.name),
        )
        chapter_files = [path for path in chapter_files if _chapter_number(path) > 0]
        existing_count = max((_chapter_number(path) for path in chapter_files), default=0)

        recent_files = chapter_files[-3:]
        recent_chapters = "\n\n".join(
            f"## {path.name}\n{_tail_text(path.read_text(encoding='utf-8'), 6000)}"
            for path in recent_files
        )
        intro = _read_optional(chapters_dir / "00-简介.md")
        source_material = "\n\n".join(
            part
            for part in [
                f"# 素材目录\n{source_dir}",
                f"# 简介\n{intro}",
                f"# SUMMARY\n{summary}",
                f"# 最近章节\n{recent_chapters}",
            ]
            if part.strip()
        )

        return {
            "source_dir": str(source_dir),
            "characters": characters or state["characters"],
            "outline": summary or state["outline"],
            "source_material": source_material,
            "continuity_notes": source_material,
            "last_chapter_summary": recent_chapters,
            "existing_chapters_count": existing_count,
            "current_chapter": existing_count + 1,
        }

    def plan_chapter(state: NovelState):
        return {"chapter_plan": call(chapter_plan_prompt(state))}

    def write_chapter(state: NovelState):
        draft = call(draft_prompt(state))
        return {"drafts": [*state["drafts"], draft]}

    def critique_chapter(state: NovelState):
        return {"critique": call(critique_prompt(state))}

    def revise_chapter(state: NovelState):
        revised = call(revise_prompt(state))
        return {"drafts": [*state["drafts"][:-1], revised]}

    def update_continuity(state: NovelState):
        summary = call(summarize_prompt(state))
        return {
            "last_chapter_summary": summary,
            "continuity_notes": summary,
            "current_chapter": state["current_chapter"] + 1,
            "generated_chapters_count": state["generated_chapters_count"] + 1,
        }

    def should_continue(state: NovelState):
        if state["generated_chapters_count"] >= state["max_chapters"]:
            return "finish"
        return "next_chapter"

    def after_source_material(state: NovelState):
        if state.get("mode") == "continue":
            return "continue_existing"
        return "build_new"

    if studio_input:
        graph = StateGraph(NovelState, input_schema=NovelInput)
    else:
        graph = StateGraph(NovelState)

    def initialize(state: NovelInput):
        return initial_state_from_input(state)

    if studio_input:
        graph.add_node("initialize", initialize)
    graph.add_node("load_source_material", load_source_material)
    graph.add_node("build_world", build_world)
    graph.add_node("build_characters", build_characters)
    graph.add_node("build_outline", build_outline)
    graph.add_node("plan_chapter", plan_chapter)
    graph.add_node("write_chapter", write_chapter)
    graph.add_node("critique_chapter", critique_chapter)
    graph.add_node("revise_chapter", revise_chapter)
    graph.add_node("update_continuity", update_continuity)

    if studio_input:
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "load_source_material")
    else:
        graph.add_edge(START, "load_source_material")
    graph.add_conditional_edges(
        "load_source_material",
        after_source_material,
        {
            "continue_existing": "plan_chapter",
            "build_new": "build_world",
        },
    )
    graph.add_edge("build_world", "build_characters")
    graph.add_edge("build_characters", "build_outline")
    graph.add_edge("build_outline", "plan_chapter")
    graph.add_edge("plan_chapter", "write_chapter")
    graph.add_edge("write_chapter", "critique_chapter")
    graph.add_edge("critique_chapter", "revise_chapter")
    graph.add_edge("revise_chapter", "update_continuity")
    graph.add_conditional_edges(
        "update_continuity",
        should_continue,
        {
            "next_chapter": "plan_chapter",
            "finish": END,
        },
    )

    return graph.compile()


def _read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _chapter_number(path: Path) -> int:
    match = re.match(r"(\d+)", path.name)
    return int(match.group(1)) if match else 0


def _tail_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]
