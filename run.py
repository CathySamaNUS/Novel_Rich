from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from novel_agent.graph import build_graph
from novel_agent.models import ModelConfig, build_model
from novel_agent.output import write_project
from novel_agent.state import initial_state


def parse_args():
    parser = argparse.ArgumentParser(description="Run the LangGraph novel agent.")
    parser.add_argument("--idea", required=True, help="小说核心创意")
    parser.add_argument("--genre", default="女频、强情绪、爽文", help="类型")
    parser.add_argument(
        "--style",
        default="快节奏、强冲突、对白有拉扯、章节结尾有钩子",
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
    state = initial_state(
        idea=args.idea,
        genre=args.genre,
        style=args.style,
        mode=args.mode,
        source_dir=args.source_dir,
        max_chapters=args.max_chapters,
        words_per_chapter=args.words_per_chapter,
    )
    result = app.invoke(state)
    output_dir = write_project(result, Path(args.output))
    print(f"Done: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
