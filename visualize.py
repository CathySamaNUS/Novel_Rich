from __future__ import annotations

from pathlib import Path

from novel_agent.graph import build_graph
from novel_agent.models import DryRunModel


def main():
    app = build_graph(DryRunModel())
    graph = app.get_graph()
    output_dir = Path("diagrams")
    output_dir.mkdir(exist_ok=True)

    mermaid = graph.draw_mermaid()
    (output_dir / "novel_agent_flow.mmd").write_text(mermaid, encoding="utf-8")
    (output_dir / "novel_agent_flow.md").write_text(
        f"# Novel Agent Flow\n\n```mermaid\n{mermaid}\n```\n",
        encoding="utf-8",
    )
    print(f"Done: {(output_dir / 'novel_agent_flow.md').resolve()}")


if __name__ == "__main__":
    main()

