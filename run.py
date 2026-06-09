from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from langgraph.types import Command

from novel_agent.graph import build_graph
from novel_agent.models import ModelConfig, build_model
from novel_agent.output import write_project
from novel_agent.state import (
    DEFAULT_GENRE,
    DEFAULT_SKILL_EVOLUTION_WINDOW,
    DEFAULT_SKILL_FAILURE_THRESHOLD,
    DEFAULT_STYLE,
    initial_state_from_input,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the LangGraph novel agent.")
    parser.add_argument("--idea", default="", help="小说核心创意；continue 模式可留空")
    parser.add_argument("--genre", default=DEFAULT_GENRE, help="类型")
    parser.add_argument("--style", default=DEFAULT_STYLE, help="文风")
    parser.add_argument("--max-chapters", type=int, default=3, help="生成章节数")
    parser.add_argument("--words-per-chapter", type=int, default=1800, help="每章目标字数")
    parser.add_argument("--model", default="gpt-4.1-mini", help="OpenAI 模型名")
    parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "deepseek"],
        help="模型供应商",
    )
    parser.add_argument("--temperature", type=float, default=0.8, help="生成温度")
    parser.add_argument("--dry-run", action="store_true", help="不用 API key，只验证流程")
    parser.add_argument(
        "--mode",
        default="new",
        choices=["new", "continue"],
        help="new 从零创作；continue 读取 source-dir 续写",
    )
    parser.add_argument("--source-dir", default="", help="已有小说素材目录")
    parser.add_argument(
        "--output",
        default="output",
        help="输出目录，默认写到当前项目的 output",
    )
    parser.add_argument(
        "--enable-writing-skill",
        action="store_true",
        help="开启写作 skill 分层注入",
    )
    parser.add_argument(
        "--enable-skill-evolution",
        action="store_true",
        help="开启 batch 级小说特定 skill 演化 gate",
    )
    parser.add_argument(
        "--enable-memory-evolution",
        action="store_true",
        help="开启 batch 级人设/主线记忆演化 gate（默认随 --enable-skill-evolution 自动开）",
    )
    parser.add_argument(
        "--disable-memory-evolution",
        action="store_true",
        help="即使开了 skill-evolution 也不触发 memory 演化",
    )
    parser.add_argument(
        "--skill-evolution-window",
        type=int,
        default=DEFAULT_SKILL_EVOLUTION_WINDOW,
        help="累计多少章后才允许触发 skill 演化",
    )
    parser.add_argument(
        "--skill-failure-threshold",
        type=int,
        default=DEFAULT_SKILL_FAILURE_THRESHOLD,
        help="累计窗口内至少多少次高失败才触发 skill 演化",
    )
    parser.add_argument(
        "--skip-review",
        action="store_true",
        help="跳过人工审阅节点，章节生成后自动确认",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="保留审阅流程配置，但在 CLI 下自动通过，适合 dry-run 或批量测试",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_args()

    model = build_model(
        ModelConfig(
            model=args.model,
            temperature=args.temperature,
            dry_run=args.dry_run,
            provider=args.provider,
        )
    )
    app = build_graph(model)
    state = initial_state_from_input(
        {
            "idea": args.idea,
            "genre": args.genre,
            "style": args.style,
            "mode": args.mode,
            "source_dir": args.source_dir,
            "output_dir": args.output,
            "enable_writing_skill": args.enable_writing_skill or args.enable_skill_evolution,
            "enable_skill_evolution": args.enable_skill_evolution,
            "enable_memory_evolution": (
                False
                if args.disable_memory_evolution
                else (args.enable_memory_evolution or args.enable_skill_evolution)
            ),
            "skill_evolution_window": args.skill_evolution_window,
            "skill_failure_threshold": args.skill_failure_threshold,
            "max_chapters": args.max_chapters,
            "words_per_chapter": args.words_per_chapter,
            "review_required": not args.skip_review,
            "auto_approve": args.auto_approve or args.dry_run,
        }
    )
    config = {"configurable": {"thread_id": f"cli-{uuid4().hex}"}, "recursion_limit": max(50, args.max_chapters * 20)}
    result = app.invoke(state, config=config)
    while "__interrupt__" in result:
        decision = _prompt_review_decision(result["__interrupt__"])
        result = app.invoke(Command(resume=decision), config=config)

    output_dir = write_project(result, Path(args.output))
    print(f"Done: {output_dir.resolve()}")


def _prompt_review_decision(interrupts):
    review = interrupts[0].value if interrupts else {}
    chapter = review.get("chapter", "?")

    if review.get("type") == "skill_update_review":
        print(f"\n=== 第 {chapter} 章 Skill 更新审阅 ===")
        _print_block("当前单本小说 Skill", review.get("current_skill", ""))
        _print_block("Skill 更新建议", review.get("suggestion", ""))
        while True:
            action = input("选择操作 [a=apply/e=edit/s=skip]: ").strip().lower()
            if action in {"a", "apply", ""}:
                return {"action": "apply"}
            if action in {"e", "edit"}:
                print("粘贴你修改后的 skill 更新内容，单独输入 EOF 结束：")
                edited_text = _read_multiline_input()
                if edited_text.strip():
                    return {"action": "edit", "edited_text": edited_text}
                print("未输入内容，重新选择。")
                continue
            if action in {"s", "skip"}:
                return {"action": "skip"}
            print("无效输入，请重新选择。")

    if review.get("type") == "memory_update_review":
        print(f"\n=== 第 {chapter} 章 人设/主线 更新审阅 ===")
        _print_block("当前 characters", review.get("current_characters", ""))
        _print_block("当前 plot_memory", review.get("current_plot_memory", ""))
        _print_block("更新建议", review.get("suggestion", ""))
        while True:
            action = input("选择操作 [a=apply/e=edit/s=skip]: ").strip().lower()
            if action in {"a", "apply", ""}:
                return {"action": "apply"}
            if action in {"e", "edit"}:
                print("粘贴你修改后的人设/主线更新内容，单独输入 EOF 结束：")
                edited_text = _read_multiline_input()
                if edited_text.strip():
                    return {"action": "edit", "edited_text": edited_text}
                print("未输入内容，重新选择。")
                continue
            if action in {"s", "skip"}:
                return {"action": "skip"}
            print("无效输入，请重新选择。")

    print(f"\n=== 第 {chapter} 章人工审阅 ===")
    _print_block("章节规划", review.get("plan", ""))
    _print_block("正文", review.get("draft", ""))
    _print_block("审校意见", review.get("critique", ""))
    _print_block("重生成建议", review.get("regenerate_brief", ""))

    while True:
        raw = input(
            "选择操作 [a=approve/r=regenerate/e=edit；前缀加 m 强制触发人设/主线更新，如 ma/mr]: "
        ).strip().lower()
        force_memory = False
        if raw.startswith("m") and len(raw) > 1:
            force_memory = True
            action = raw[1:]
        else:
            action = raw
        if action in {"a", "approve", ""}:
            return {"action": "approve", "force_memory_update": force_memory}
        if action in {"r", "regenerate"}:
            feedback = input("输入重生成反馈（留空则直接采用上面的重生成建议）: ").strip()
            return {
                "action": "regenerate",
                "feedback": feedback,
                "force_memory_update": force_memory,
            }
        if action in {"e", "edit"}:
            print("粘贴你修改后的完整正文，单独输入 EOF 结束：")
            edited_text = _read_multiline_input()
            if edited_text.strip():
                return {
                    "action": "edit",
                    "edited_text": edited_text,
                    "force_memory_update": force_memory,
                }
            print("未输入正文，重新选择。")
            continue
        print("无效输入，请重新选择。")


def _print_block(title: str, content: str):
    print(f"\n--- {title} ---")
    print((content or "").strip() or "<empty>")


def _read_multiline_input() -> str:
    lines = []
    while True:
        line = input()
        if line == "EOF":
            break
        lines.append(line)
    return "\n".join(lines)


if __name__ == "__main__":
    main()
