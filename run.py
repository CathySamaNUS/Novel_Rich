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
    DEFAULT_STYLE,
    initial_state_from_input,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the LangGraph novel agent.")
    parser.add_argument("--idea", default="", help="小说核心创意；continue 模式可留空")
    parser.add_argument("--genre", default=DEFAULT_GENRE, help="类型")
    parser.add_argument(
        "--style",
        default=DEFAULT_STYLE,
        help="文风",
    )
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
            "max_chapters": args.max_chapters,
            "words_per_chapter": args.words_per_chapter,
            "review_required": not args.skip_review,
            "auto_approve": args.auto_approve or args.dry_run,
        }
    )
    config = {"configurable": {"thread_id": f"cli-{uuid4().hex}"}}
    result = app.invoke(state, config=config)
    while "__interrupt__" in result:
        decision = _prompt_review_decision(result["__interrupt__"])
        result = app.invoke(Command(resume=decision), config=config)

    output_dir = write_project(result, Path(args.output))
    print(f"Done: {output_dir.resolve()}")


def _prompt_review_decision(interrupts):
    review = interrupts[0].value if interrupts else {}
    chapter = review.get("chapter", "?")
    print(f"\n=== 第 {chapter} 章人工审阅 ===")
    _print_block("章节规划", review.get("plan", ""))
    _print_block("正文", review.get("draft", ""))
    _print_block("审校意见", review.get("critique", ""))

    while True:
        action = input("选择操作 [a=approve/r=regenerate/e=edit]: ").strip().lower()
        if action in {"a", "approve", ""}:
            return {"action": "approve"}
        if action in {"r", "regenerate"}:
            feedback = input("输入重生成反馈（可留空）: ").strip()
            return {"action": "regenerate", "feedback": feedback}
        if action in {"e", "edit"}:
            print("粘贴你修改后的完整正文，单独输入 EOF 结束：")
            edited_text = _read_multiline_input()
            if edited_text.strip():
                return {"action": "edit", "edited_text": edited_text}
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
