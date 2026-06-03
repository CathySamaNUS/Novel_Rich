from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .prompts import (
    bootstrap_character_state_prompt,
    bootstrap_plot_memory_prompt,
    chapter_plan_prompt,
    character_prompt,
    critique_prompt,
    draft_prompt,
    outline_prompt,
    summarize_prompt,
    update_character_state_prompt,
    update_plot_memory_prompt,
    world_prompt,
)
from .state import NovelInput, NovelState, initial_state_from_input


def build_graph(model, *, studio_input: bool = False):
    def call(prompt: str) -> str:
        response = model.invoke(prompt)
        return getattr(response, "content", str(response))

    def build_world(state: NovelState):
        return {"world_bible": call(world_prompt(state))}

    def build_characters(state: NovelState):
        return {"characters": call(character_prompt(state))}

    def build_outline(state: NovelState):
        return {"outline": call(outline_prompt(state))}

    def load_source_material(state: NovelState):
        if state.get("mode") != "continue":
            return {}

        source_dir_value = (state.get("source_dir") or "").strip()
        if not source_dir_value:
            raise ValueError("source_dir is required when mode=continue")

        source_dir = Path(source_dir_value).expanduser()
        if not source_dir.exists():
            raise FileNotFoundError(f"source_dir not found: {source_dir}")

        world_bible = _first_existing(
            source_dir / "world_bible.md",
            source_dir / "世界观设定.md",
        )
        characters = _first_existing(
            source_dir / "characters.md",
            source_dir / "人物设定.md",
        )
        outline = _first_existing(
            source_dir / "outline.md",
            source_dir / "SUMMARY.md",
        )
        continuity_notes = _read_optional(source_dir / "continuity_notes.md")
        last_chapter_summary = _read_optional(source_dir / "last_chapter_summary.md")
        character_state = _read_optional(source_dir / "character_state.md")
        plot_memory = _read_optional(source_dir / "plot_memory.md")

        chapters_dir = source_dir / "chapters"
        chapter_files = sorted(
            chapters_dir.glob("*.md"),
            key=lambda path: (_chapter_number_from_name(path.name), path.name),
        )
        chapter_files = [
            path for path in chapter_files if _chapter_number_from_name(path.name) > 0
        ]
        existing_count = max(
            (_chapter_number_from_name(path.name) for path in chapter_files), default=0
        )

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
                f"# 大纲/总结\n{outline}",
                f"# 最近章节\n{recent_chapters}",
            ]
            if part.strip()
        )

        return {
            "source_dir": str(source_dir),
            "world_bible": world_bible or state["world_bible"],
            "characters": characters or state["characters"],
            "outline": outline or state["outline"],
            "source_material": source_material,
            "continuity_notes": continuity_notes or source_material,
            "last_chapter_summary": last_chapter_summary or recent_chapters,
            "character_state": character_state or state["character_state"],
            "plot_memory": plot_memory or state["plot_memory"],
            "existing_chapters_count": existing_count,
            "current_chapter": existing_count + 1,
        }

    def bootstrap_character_state(state: NovelState):
        if state["character_state"].strip():
            return {}
        return {"character_state": call(bootstrap_character_state_prompt(state))}

    def bootstrap_plot_memory(state: NovelState):
        if state["plot_memory"].strip():
            return {}
        return {"plot_memory": call(bootstrap_plot_memory_prompt(state))}

    def plan_chapter(state: NovelState):
        return {"current_chapter_plan": call(chapter_plan_prompt(state))}

    def write_chapter(state: NovelState):
        return {"current_draft": call(draft_prompt(state))}

    def critique_chapter(state: NovelState):
        return {"current_critique": call(critique_prompt(state))}

    def human_review(state: NovelState):
        if not state["review_required"] or state["auto_approve"]:
            return {
                "current_review_action": "approve",
                "current_human_feedback": "",
                "current_human_edit": "",
            }

        decision = interrupt(
            {
                "type": "chapter_review",
                "chapter": state["current_chapter"],
                "plan": state["current_chapter_plan"],
                "draft": state["current_draft"],
                "critique": state["current_critique"],
                "instructions": {
                    "approve": "确认这一章可以入库并更新记忆",
                    "regenerate": "提供反馈，基于同一章重新生成",
                    "edit": "你直接修改正文，修改后作为最终版本保存",
                },
            }
        )
        return _normalize_review_decision(decision, state)

    def apply_human_edit(state: NovelState):
        edited_text = (state["current_human_edit"] or "").strip()
        if not edited_text:
            return {"current_review_action": "approve"}
        return {"current_draft": edited_text, "current_review_action": "approve"}

    def summarize_chapter(state: NovelState):
        summary = call(summarize_prompt(state))
        return {
            "last_chapter_summary": summary,
            "continuity_notes": _append_continuity_notes(
                state["continuity_notes"], state["current_chapter"], summary
            ),
        }

    def update_character_state(state: NovelState):
        return {"character_state": call(update_character_state_prompt(state))}

    def update_plot_memory(state: NovelState):
        return {"plot_memory": call(update_plot_memory_prompt(state))}

    def finalize_chapter(state: NovelState):
        return {
            "approved_chapter_plans": [
                *state["approved_chapter_plans"],
                state["current_chapter_plan"],
            ],
            "approved_drafts": [*state["approved_drafts"], state["current_draft"]],
            "approved_critiques": [
                *state["approved_critiques"],
                state["current_critique"],
            ],
            "approved_summaries": [
                *state["approved_summaries"],
                state["last_chapter_summary"],
            ],
            "current_chapter": state["current_chapter"] + 1,
            "generated_chapters_count": state["generated_chapters_count"] + 1,
            "current_chapter_plan": "",
            "current_draft": "",
            "current_critique": "",
            "current_review_action": "",
            "current_human_feedback": "",
            "current_human_edit": "",
        }

    def should_continue(state: NovelState):
        if state["generated_chapters_count"] >= state["max_chapters"]:
            return "finish"
        return "next_chapter"

    def route_after_load(state: NovelState):
        if state.get("mode") == "continue":
            if _has_dynamic_memory(state):
                return "plan_chapter"
            return "bootstrap_character_state"
        return "build_world"

    def route_after_character_state(state: NovelState):
        if state["plot_memory"].strip():
            return "plan_chapter"
        return "bootstrap_plot_memory"

    def route_after_review(state: NovelState):
        action = state["current_review_action"]
        if action == "approve":
            return "summarize_chapter"
        if action == "edit":
            return "apply_human_edit"
        return "write_chapter"

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
    graph.add_node("bootstrap_character_state", bootstrap_character_state)
    graph.add_node("bootstrap_plot_memory", bootstrap_plot_memory)
    graph.add_node("plan_chapter", plan_chapter)
    graph.add_node("write_chapter", write_chapter)
    graph.add_node("critique_chapter", critique_chapter)
    graph.add_node("human_review", human_review)
    graph.add_node("apply_human_edit", apply_human_edit)
    graph.add_node("summarize_chapter", summarize_chapter)
    graph.add_node("update_character_state", update_character_state)
    graph.add_node("update_plot_memory", update_plot_memory)
    graph.add_node("finalize_chapter", finalize_chapter)

    if studio_input:
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "load_source_material")
    else:
        graph.add_edge(START, "load_source_material")

    graph.add_conditional_edges(
        "load_source_material",
        route_after_load,
        {
            "build_world": "build_world",
            "bootstrap_character_state": "bootstrap_character_state",
            "plan_chapter": "plan_chapter",
        },
    )
    graph.add_edge("build_world", "build_characters")
    graph.add_edge("build_characters", "build_outline")
    graph.add_edge("build_outline", "bootstrap_character_state")
    graph.add_conditional_edges(
        "bootstrap_character_state",
        route_after_character_state,
        {
            "bootstrap_plot_memory": "bootstrap_plot_memory",
            "plan_chapter": "plan_chapter",
        },
    )
    graph.add_edge("bootstrap_plot_memory", "plan_chapter")
    graph.add_edge("plan_chapter", "write_chapter")
    graph.add_edge("write_chapter", "critique_chapter")
    graph.add_edge("critique_chapter", "human_review")
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "summarize_chapter": "summarize_chapter",
            "apply_human_edit": "apply_human_edit",
            "write_chapter": "write_chapter",
        },
    )
    graph.add_edge("apply_human_edit", "summarize_chapter")
    graph.add_edge("summarize_chapter", "update_character_state")
    graph.add_edge("update_character_state", "update_plot_memory")
    graph.add_edge("update_plot_memory", "finalize_chapter")
    graph.add_conditional_edges(
        "finalize_chapter",
        should_continue,
        {
            "next_chapter": "plan_chapter",
            "finish": END,
        },
    )

    return graph.compile(checkpointer=InMemorySaver())


def _normalize_review_decision(decision, state: NovelState):
    if isinstance(decision, str):
        action = decision.strip().lower()
        return {
            "current_review_action": action or "approve",
            "current_human_feedback": "",
            "current_human_edit": state["current_draft"] if action == "edit" else "",
        }

    if not isinstance(decision, dict):
        return {
            "current_review_action": "approve",
            "current_human_feedback": "",
            "current_human_edit": "",
        }

    action = str(decision.get("action") or "approve").strip().lower()
    if action not in {"approve", "regenerate", "edit"}:
        action = "approve"

    human_edit = str(decision.get("edited_text") or "")
    if action == "edit" and not human_edit.strip():
        human_edit = state["current_draft"]

    return {
        "current_review_action": action,
        "current_human_feedback": str(decision.get("feedback") or "").strip(),
        "current_human_edit": human_edit,
    }


def _has_dynamic_memory(state: NovelState) -> bool:
    return bool(state["character_state"].strip() and state["plot_memory"].strip())


def _read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _first_existing(*paths: Path) -> str:
    for path in paths:
        content = _read_optional(path)
        if content.strip():
            return content
    return ""


def _chapter_number_from_name(name: str) -> int:
    digits = []
    for char in name:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    return int("".join(digits)) if digits else 0


def _append_continuity_notes(existing: str, chapter_number: int, summary: str) -> str:
    entry = f"## 第{chapter_number}章\n{summary.strip()}"
    if not existing.strip():
        return entry
    return f"{existing.rstrip()}\n\n{entry}"


def _tail_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]
