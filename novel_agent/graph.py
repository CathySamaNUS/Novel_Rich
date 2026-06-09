from __future__ import annotations

from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .output import slugify, write_project
from .prompts import (
    bootstrap_character_state_prompt,
    bootstrap_plot_memory_prompt,
    chapter_plan_prompt,
    character_prompt,
    critique_prompt,
    draft_prompt,
    memory_reflection_prompt,
    outline_prompt,
    regenerate_brief_prompt,
    skill_reflection_prompt,
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

    def validate_memory_files(state: NovelState):
        """Preflight: 自检并补建必要的 md 文件 / 重定向 source_dir。

        - 强制触发 prompts._load_system_rules（若 ./system_prompt.md 缺失会自动写默认值）
        - 计算 work_dir = output_dir / slugify(idea)，mkdir -p
        - Continue 模式下：若 work_dir 已有完整 md（characters / outline / world_bible），把
          source_dir 重定向到 work_dir，让后续 load_source_material 读到上一次跑的产物
        - 对缺失的核心 md 文件创建占位（确保后续节点和 _read_optional 行为一致）
        """
        # 触发 system_prompt.md 自检
        from . import prompts as _prompts_module  # 避免循环 import 时序

        _prompts_module.SYSTEM_RULES = _prompts_module._load_system_rules()

        output_dir = (state.get("output_dir") or "output").strip() or "output"
        idea = state.get("idea") or ""
        slug = slugify(idea)
        work_dir = Path(output_dir) / slug
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # 只读环境下也不要 crash 整个 run
            pass

        patch: dict = {"output_dir": output_dir}

        # Continue 模式优先级重排
        if state.get("mode") == "continue":
            has_full_set = (
                (work_dir / "characters.md").exists()
                and (work_dir / "outline.md").exists()
                and (work_dir / "world_bible.md").exists()
            )
            if has_full_set:
                patch["source_dir"] = str(work_dir)

        # 占位：缺失的 md 创建空文件，让 _read_optional 找得到
        placeholder_files = [
            "world_bible.md",
            "characters.md",
            "character_state.md",
            "outline.md",
            "plot_memory.md",
            "continuity_notes.md",
            "last_chapter_summary.md",
        ]
        if state.get("enable_writing_skill"):
            placeholder_files.extend(
                ["shared_writing_skill.md", "novel_writing_skill.md"]
            )
        for name in placeholder_files:
            target = work_dir / name
            if not target.exists():
                try:
                    target.touch()
                except OSError:
                    pass

        return patch

    def persist_to_disk(state: NovelState):
        """每章末尾把 state 落到 output/<slug>/ 下的 md 文件。

        让 Studio / CLI 行为一致：每章结束都有完整产物落盘，下次 continue 模式可直接读到。
        失败不阻断 graph 执行——只 log 不抛。
        """
        output_root = Path((state.get("output_dir") or "output").strip() or "output")
        try:
            write_project(state, output_root)
        except Exception as exc:  # noqa: BLE001
            print(f"[persist_to_disk] write_project failed: {exc}")
        return {}

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
        shared_skill = ""
        novel_skill = ""
        if state.get("enable_writing_skill"):
            shared_skill = _first_existing(
                source_dir / "shared_writing_skill.md",
                source_dir / "shared_skill.md",
                source_dir / "通用写作技能.md",
            )
            novel_skill = _first_existing(
                source_dir / "novel_writing_skill.md",
                source_dir / "writing_skill.md",
                source_dir / "skill.md",
                source_dir / "写作技能.md",
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
            (_chapter_number_from_name(path.name) for path in chapter_files),
            default=0,
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
            "shared_writing_skill": shared_skill or state["shared_writing_skill"],
            "novel_writing_skill": novel_skill or state["novel_writing_skill"],
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

    def condense_regenerate_brief(state: NovelState):
        return {"current_regenerate_brief": call(regenerate_brief_prompt(state))}

    def reflect_writing_skill(state: NovelState):
        if not _should_reflect_writing_skill(state):
            return {
                "current_skill_update_suggestion": "",
                "current_skill_review_action": "skip",
                "current_skill_edit": "",
            }

        suggestion = call(skill_reflection_prompt(state))
        if not _suggests_skill_update(suggestion):
            return {
                "current_skill_update_suggestion": suggestion,
                "current_skill_review_action": "skip",
                "current_skill_edit": "",
            }
        return {"current_skill_update_suggestion": suggestion}

    def review_skill_update(state: NovelState):
        suggestion = (state["current_skill_update_suggestion"] or "").strip()
        if not suggestion or not _suggests_skill_update(suggestion):
            return {"current_skill_review_action": "skip", "current_skill_edit": ""}

        if not state["review_required"] or state["auto_approve"]:
            return {
                "current_skill_review_action": "apply",
                "current_skill_edit": suggestion,
            }

        decision = interrupt(
            {
                "type": "skill_update_review",
                "chapter": state["current_chapter"],
                "current_skill": state["novel_writing_skill"],
                "suggestion": suggestion,
                "instructions": {
                    "apply": "采用这份小说特定 skill 更新建议",
                    "edit": "修改后再采用",
                    "skip": "本批次不更新小说特定 skill",
                },
            }
        )
        return _normalize_skill_review_decision(decision, state)

    def apply_skill_update(state: NovelState):
        skill_text = (
            state["current_skill_edit"] or state["current_skill_update_suggestion"] or ""
        ).strip()
        skill_patch = _extract_skill_patch(skill_text)
        if not skill_patch:
            return {"current_skill_review_action": "skip"}

        merged_skill = _merge_writing_skill(state["novel_writing_skill"], skill_patch)
        if merged_skill == state["novel_writing_skill"]:
            return {"current_skill_review_action": "skip"}

        return {
            "novel_writing_skill": merged_skill,
            "approved_skill_updates": [
                *state["approved_skill_updates"],
                f"## 第{state['current_chapter']}章\n{skill_patch}",
            ],
            "current_skill_review_action": "applied",
            "recent_critiques": [],
            "recent_human_feedback": [],
            "recent_failure_flags": [],
        }

    def reflect_memory(state: NovelState):
        """对人设 / 主线记忆做 batch 反思。镜像 reflect_writing_skill 的逻辑。"""
        if not (_should_reflect_memory(state) or state.get("force_memory_flag")):
            return {
                "current_memory_update_suggestion": "",
                "current_memory_review_action": "skip",
                "current_memory_edit": "",
            }

        suggestion = call(memory_reflection_prompt(state))
        if not _suggests_memory_update(suggestion):
            return {
                "current_memory_update_suggestion": suggestion,
                "current_memory_review_action": "skip",
                "current_memory_edit": "",
            }
        return {"current_memory_update_suggestion": suggestion}

    def review_memory_update(state: NovelState):
        suggestion = (state["current_memory_update_suggestion"] or "").strip()
        if not suggestion or not _suggests_memory_update(suggestion):
            return {
                "current_memory_review_action": "skip",
                "current_memory_edit": "",
            }

        if not state["review_required"] or state["auto_approve"]:
            return {
                "current_memory_review_action": "apply",
                "current_memory_edit": suggestion,
            }

        decision = interrupt(
            {
                "type": "memory_update_review",
                "chapter": state["current_chapter"],
                "current_characters": state["characters"],
                "current_plot_memory": state["plot_memory"],
                "suggestion": suggestion,
                "instructions": {
                    "apply": "采用人设/主线更新建议",
                    "edit": "修改后再采用",
                    "skip": "本批次不动人设和主线",
                },
            }
        )
        return _normalize_memory_review_decision(decision, state)

    def apply_memory_update(state: NovelState):
        memory_text = (
            state["current_memory_edit"] or state["current_memory_update_suggestion"] or ""
        ).strip()
        chars_patch, plot_patch = _extract_memory_patches(memory_text)
        if not chars_patch and not plot_patch:
            return {"current_memory_review_action": "skip"}

        new_characters = state["characters"]
        new_plot_memory = state["plot_memory"]
        if chars_patch:
            new_characters = _merge_writing_skill(state["characters"], chars_patch)
        if plot_patch:
            new_plot_memory = _merge_writing_skill(state["plot_memory"], plot_patch)

        # 没有任何实质变更
        if (
            new_characters == state["characters"]
            and new_plot_memory == state["plot_memory"]
        ):
            return {"current_memory_review_action": "skip"}

        recorded_patch = []
        if chars_patch:
            recorded_patch.append(f"### characters\n{chars_patch}")
        if plot_patch:
            recorded_patch.append(f"### plot_memory\n{plot_patch}")
        record = f"## 第{state['current_chapter']}章\n" + "\n\n".join(recorded_patch)

        return {
            "characters": new_characters,
            "plot_memory": new_plot_memory,
            "approved_memory_updates": [
                *state["approved_memory_updates"],
                record,
            ],
            "current_memory_review_action": "applied",
        }

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
                "regenerate_brief": state["current_regenerate_brief"],
                "instructions": {
                    "approve": "确认这一章可以入库并更新记忆",
                    "regenerate": "会先重做章节规划，再按反馈重写本章",
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

    def record_skill_signal(state: NovelState):
        feedback_note = (state.get("current_chapter_feedback_log") or "").strip()
        recent_critiques = [
            *state["recent_critiques"],
            _truncate_item(state["current_critique"], 2000),
        ][-state["skill_evolution_window"] :]
        recent_feedback = [
            *state["recent_human_feedback"],
            feedback_note,
        ][-state["skill_evolution_window"] :]
        recent_failure_flags = [
            *state["recent_failure_flags"],
            _chapter_failure_flag(state),
        ][-state["skill_evolution_window"] :]
        return {
            "recent_critiques": recent_critiques,
            "recent_human_feedback": recent_feedback,
            "recent_failure_flags": recent_failure_flags,
        }

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

    def route_after_critique(state: NovelState):
        return "condense_regenerate_brief"

    def route_after_review(state: NovelState):
        action = state["current_review_action"]
        if action == "approve":
            return "summarize_chapter"
        if action == "edit":
            return "apply_human_edit"
        return "plan_chapter"

    def route_after_record_skill_signal(state: NovelState):
        if _should_reflect_writing_skill(state):
            return "reflect_writing_skill"
        if _memory_path_active(state):
            return "reflect_memory"
        return "finalize_chapter"

    def route_after_skill_review(state: NovelState):
        action = state["current_skill_review_action"]
        if action in {"apply", "edit"}:
            return "apply_skill_update"
        if _memory_path_active(state):
            return "reflect_memory"
        return "finalize_chapter"

    def route_after_skill_apply(state: NovelState):
        if _memory_path_active(state):
            return "reflect_memory"
        return "finalize_chapter"

    def route_after_memory_review(state: NovelState):
        action = state["current_memory_review_action"]
        if action in {"apply", "edit"}:
            return "apply_memory_update"
        return "finalize_chapter"

    if studio_input:
        graph = StateGraph(NovelState, input_schema=NovelInput)
    else:
        graph = StateGraph(NovelState)

    def initialize(state: NovelInput):
        return initial_state_from_input(state)

    if studio_input:
        graph.add_node("initialize", initialize)

    graph.add_node("validate_memory_files", validate_memory_files)
    graph.add_node("load_source_material", load_source_material)
    graph.add_node("build_world", build_world)
    graph.add_node("build_characters", build_characters)
    graph.add_node("build_outline", build_outline)
    graph.add_node("bootstrap_character_state", bootstrap_character_state)
    graph.add_node("bootstrap_plot_memory", bootstrap_plot_memory)
    graph.add_node("plan_chapter", plan_chapter)
    graph.add_node("write_chapter", write_chapter)
    graph.add_node("critique_chapter", critique_chapter)
    graph.add_node("condense_regenerate_brief", condense_regenerate_brief)
    graph.add_node("human_review", human_review)
    graph.add_node("apply_human_edit", apply_human_edit)
    graph.add_node("summarize_chapter", summarize_chapter)
    graph.add_node("update_character_state", update_character_state)
    graph.add_node("update_plot_memory", update_plot_memory)
    graph.add_node("record_skill_signal", record_skill_signal)
    graph.add_node("reflect_writing_skill", reflect_writing_skill)
    graph.add_node("review_skill_update", review_skill_update)
    graph.add_node("apply_skill_update", apply_skill_update)
    graph.add_node("reflect_memory", reflect_memory)
    graph.add_node("review_memory_update", review_memory_update)
    graph.add_node("apply_memory_update", apply_memory_update)
    graph.add_node("persist_to_disk", persist_to_disk)
    graph.add_node("finalize_chapter", finalize_chapter)

    if studio_input:
        graph.add_edge(START, "initialize")
        graph.add_edge("initialize", "validate_memory_files")
    else:
        graph.add_edge(START, "validate_memory_files")
    graph.add_edge("validate_memory_files", "load_source_material")

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
    graph.add_conditional_edges(
        "critique_chapter",
        route_after_critique,
        {"condense_regenerate_brief": "condense_regenerate_brief"},
    )
    graph.add_edge("condense_regenerate_brief", "human_review")
    graph.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "summarize_chapter": "summarize_chapter",
            "apply_human_edit": "apply_human_edit",
            "plan_chapter": "plan_chapter",
        },
    )
    graph.add_edge("apply_human_edit", "summarize_chapter")
    graph.add_edge("summarize_chapter", "update_character_state")
    graph.add_edge("update_character_state", "update_plot_memory")
    graph.add_edge("update_plot_memory", "record_skill_signal")
    graph.add_conditional_edges(
        "record_skill_signal",
        route_after_record_skill_signal,
        {
            "reflect_writing_skill": "reflect_writing_skill",
            "reflect_memory": "reflect_memory",
            "finalize_chapter": "finalize_chapter",
        },
    )
    graph.add_edge("reflect_writing_skill", "review_skill_update")
    graph.add_conditional_edges(
        "review_skill_update",
        route_after_skill_review,
        {
            "apply_skill_update": "apply_skill_update",
            "reflect_memory": "reflect_memory",
            "finalize_chapter": "finalize_chapter",
        },
    )
    graph.add_conditional_edges(
        "apply_skill_update",
        route_after_skill_apply,
        {
            "reflect_memory": "reflect_memory",
            "finalize_chapter": "finalize_chapter",
        },
    )
    graph.add_edge("reflect_memory", "review_memory_update")
    graph.add_conditional_edges(
        "review_memory_update",
        route_after_memory_review,
        {
            "apply_memory_update": "apply_memory_update",
            "finalize_chapter": "finalize_chapter",
        },
    )
    graph.add_edge("apply_memory_update", "finalize_chapter")
    graph.add_edge("finalize_chapter", "persist_to_disk")
    graph.add_conditional_edges(
        "persist_to_disk",
        should_continue,
        {
            "next_chapter": "plan_chapter",
            "finish": END,
        },
    )

    if studio_input:
        return graph.compile()
    return graph.compile(checkpointer=InMemorySaver())


def _normalize_review_decision(decision, state: NovelState):
    if isinstance(decision, str):
        action = decision.strip().lower() or "approve"
        if action not in {"approve", "regenerate", "edit"}:
            action = "approve"
        feedback = state["current_regenerate_brief"] if action == "regenerate" else ""
        human_edit = state["current_draft"] if action == "edit" else ""
        feedback_log = state.get("current_chapter_feedback_log", "")
        if action == "regenerate":
            feedback_log = _append_feedback_log(feedback_log, feedback)
        return {
            "current_review_action": action,
            "current_human_feedback": feedback,
            "current_human_edit": human_edit,
            "current_chapter_had_failure": state.get("current_chapter_had_failure", False)
            or action == "regenerate",
            "current_chapter_feedback_log": feedback_log,
            "force_memory_flag": state.get("force_memory_flag", False),
        }

    if not isinstance(decision, dict):
        return {
            "current_review_action": "approve",
            "current_human_feedback": "",
            "current_human_edit": "",
            "current_chapter_had_failure": state.get("current_chapter_had_failure", False),
            "current_chapter_feedback_log": state.get("current_chapter_feedback_log", ""),
            "force_memory_flag": state.get("force_memory_flag", False),
        }

    action = str(decision.get("action") or "approve").strip().lower()
    if action not in {"approve", "regenerate", "edit"}:
        action = "approve"

    human_edit = str(decision.get("edited_text") or "")
    if action == "edit" and not human_edit.strip():
        human_edit = state["current_draft"]

    feedback = _resolve_regenerate_feedback(decision, state, action)
    feedback_log = state.get("current_chapter_feedback_log", "")
    if action == "regenerate":
        feedback_log = _append_feedback_log(feedback_log, feedback)

    force_memory = bool(decision.get("force_memory_update")) or state.get(
        "force_memory_flag", False
    )

    return {
        "current_review_action": action,
        "current_human_feedback": feedback,
        "current_human_edit": human_edit,
        "current_chapter_had_failure": state.get("current_chapter_had_failure", False)
        or action == "regenerate",
        "current_chapter_feedback_log": feedback_log,
        "force_memory_flag": force_memory,
    }


def _resolve_regenerate_feedback(decision, state: NovelState, action: str) -> str:
    if action != "regenerate":
        return str(decision.get("feedback") or "").strip()

    feedback = str(decision.get("feedback") or "").strip()
    if feedback:
        return feedback
    return state["current_regenerate_brief"]


def _normalize_skill_review_decision(decision, state: NovelState):
    if isinstance(decision, str):
        action = decision.strip().lower() or "skip"
        if action not in {"apply", "edit", "skip"}:
            action = "skip"
        return {
            "current_skill_review_action": action,
            "current_skill_edit": (
                state["current_skill_update_suggestion"] if action == "apply" else ""
            ),
        }

    if not isinstance(decision, dict):
        return {"current_skill_review_action": "skip", "current_skill_edit": ""}

    action = str(decision.get("action") or "skip").strip().lower()
    if action not in {"apply", "edit", "skip"}:
        action = "skip"

    edited_text = str(decision.get("edited_text") or "").strip()
    if action == "apply":
        edited_text = state["current_skill_update_suggestion"]
    return {
        "current_skill_review_action": action,
        "current_skill_edit": edited_text,
    }


def _chapter_failure_flag(state: NovelState) -> bool:
    critique = "".join((state.get("current_critique") or "").split())
    markers = (
        "是否需要重生成：是",
        "是否需要重生成:是",
        "需要重生成：是",
        "需要重生成:是",
    )
    return state.get("current_chapter_had_failure", False) or any(
        marker in critique for marker in markers
    )


def _should_reflect_writing_skill(state: NovelState) -> bool:
    if not state["enable_writing_skill"] or not state["enable_skill_evolution"]:
        return False

    failure_flags = state.get("recent_failure_flags") or []
    critiques = state.get("recent_critiques") or []
    if len(critiques) < state["skill_evolution_window"]:
        return False
    return sum(1 for flag in failure_flags if flag) >= state["skill_failure_threshold"]


def _should_reflect_memory(state: NovelState) -> bool:
    """复用 SkillOpt 窗口门控判断是否触发人设/主线记忆反思。"""
    if not state.get("enable_memory_evolution"):
        return False

    failure_flags = state.get("recent_failure_flags") or []
    critiques = state.get("recent_critiques") or []
    if len(critiques) < state["skill_evolution_window"]:
        return False
    return sum(1 for flag in failure_flags if flag) >= state["skill_failure_threshold"]


def _memory_path_active(state: NovelState) -> bool:
    """是否需要进入 memory 反思路径：门控达成 OR 用户 force。"""
    return state.get("force_memory_flag", False) or _should_reflect_memory(state)


def _suggests_skill_update(suggestion: str) -> bool:
    text = (suggestion or "").strip()
    if not text:
        return False
    if (
        "是否建议更新小说特定skill：否" in text
        or "是否建议更新小说特定 skill：否" in text
    ):
        return False
    if "不建议更新" in text or "无需更新" in text:
        return False
    return True


def _extract_skill_patch(suggestion: str) -> str:
    text = (suggestion or "").strip()
    if not text:
        return ""

    markers = [
        "建议写入单本小说 skill 的规则：",
        "建议写入单本小说skill的规则：",
    ]
    stop_markers = [
        "不应写入单本小说 skill 的内容：",
        "不应写入单本小说skill的内容：",
    ]
    for marker in markers:
        if marker in text:
            patch = text.split(marker, 1)[1].strip()
            for stop in stop_markers:
                if stop in patch:
                    patch = patch.split(stop, 1)[0].strip()
            if patch in {"无", "- 无", "暂无"}:
                return ""
            return patch.strip()

    return text if text.startswith(("-", "##")) else ""


def _merge_writing_skill(current_skill: str, suggestion: str) -> str:
    current = (current_skill or "").strip()
    update = (suggestion or "").strip()
    if not update:
        return current
    if update in current:
        return current

    new_lines = []
    for line in update.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in current:
            continue
        new_lines.append(line.rstrip())
    if not new_lines:
        return current

    update_block = "\n".join(new_lines)
    if not current:
        return update_block
    if "\n## 演化补丁\n" in current:
        return f"{current.rstrip()}\n{update_block}"
    return f"{current.rstrip()}\n\n## 演化补丁\n{update_block}"


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


def _append_feedback_log(existing: str, feedback: str) -> str:
    note = (feedback or "").strip()
    if not note:
        return existing
    if note in existing:
        return existing
    if not existing.strip():
        return note
    return f"{existing.rstrip()}\n\n{note}"


def _tail_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _truncate_item(text: str, limit: int) -> str:
    collapsed = " ".join((text or "").split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit] + " ...[truncated]"


def _suggests_memory_update(suggestion: str) -> bool:
    text = (suggestion or "").strip()
    if not text:
        return False
    negatives = (
        "是否建议更新人设/主线：否",
        "是否建议更新人设/主线:否",
        "是否建议更新人设：否",
        "是否建议更新人设:否",
    )
    if any(neg in text for neg in negatives):
        return False
    if "不建议更新" in text or "无需更新" in text:
        return False
    return True


def _extract_memory_patches(suggestion: str) -> tuple[str, str]:
    """解析 memory_reflection_prompt 输出，提取 characters_patch 和 plot_memory_patch。"""
    text = (suggestion or "").strip()
    if not text:
        return "", ""

    char_markers = [
        "建议写入 characters 的人设修订：",
        "建议写入characters的人设修订：",
    ]
    char_stops = [
        "不应写入 characters 的内容：",
        "不应写入characters的内容：",
        "建议写入 plot_memory 的主线修订：",
        "建议写入plot_memory的主线修订：",
    ]
    plot_markers = [
        "建议写入 plot_memory 的主线修订：",
        "建议写入plot_memory的主线修订：",
    ]
    plot_stops = [
        "不应写入 plot_memory 的内容：",
        "不应写入plot_memory的内容：",
    ]

    chars_patch = _extract_section(text, char_markers, char_stops)
    plot_patch = _extract_section(text, plot_markers, plot_stops)
    return chars_patch, plot_patch


def _extract_section(text: str, markers, stops) -> str:
    for marker in markers:
        if marker in text:
            patch = text.split(marker, 1)[1].strip()
            for stop in stops:
                if stop in patch:
                    patch = patch.split(stop, 1)[0].strip()
            if patch in {"无", "- 无", "暂无", ""}:
                return ""
            return patch.strip()
    return ""


def _normalize_memory_review_decision(decision, state: NovelState):
    if isinstance(decision, str):
        action = decision.strip().lower() or "skip"
        if action not in {"apply", "edit", "skip"}:
            action = "skip"
        return {
            "current_memory_review_action": action,
            "current_memory_edit": (
                state["current_memory_update_suggestion"] if action == "apply" else ""
            ),
        }

    if not isinstance(decision, dict):
        return {"current_memory_review_action": "skip", "current_memory_edit": ""}

    action = str(decision.get("action") or "skip").strip().lower()
    if action not in {"apply", "edit", "skip"}:
        action = "skip"

    edited_text = str(decision.get("edited_text") or "").strip()
    if action == "apply":
        edited_text = state["current_memory_update_suggestion"]
    return {
        "current_memory_review_action": action,
        "current_memory_edit": edited_text,
    }
