from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ModelConfig:
    model: str = "gpt-4.1-mini"
    temperature: float = 0.8
    dry_run: bool = False
    provider: str = "openai"


class DryRunModel:
    """Small deterministic stand-in used to verify graph flow without an API key."""

    def invoke(self, prompt: str):
        title = _extract_title(prompt)
        content = (
            f"## {title}\n\n"
            "这是 dry-run 生成内容，用于验证 LangGraph 节点、循环和文件输出。"
            "真实运行时请设置 OPENAI_API_KEY 并去掉 --dry-run。\n\n"
            f"提示词摘要：{prompt[:240].replace(chr(10), ' ')}"
        )
        return type("DryRunResponse", (), {"content": content})()


def build_model(config: ModelConfig):
    if config.dry_run:
        return DryRunModel()

    from langchain_openai import ChatOpenAI

    provider = (config.provider or "openai").lower()
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = config.model if config.model != "gpt-4.1-mini" else "deepseek-v4-flash"
        return ChatOpenAI(
            model=model,
            temperature=config.temperature,
            api_key=api_key,
            base_url=base_url,
        )

    return ChatOpenAI(model=config.model, temperature=config.temperature)


def _extract_title(prompt: str) -> str:
    for marker in ("任务：", "请生成", "请写", "请审校", "请润色"):
        if marker in prompt:
            after = prompt.split(marker, 1)[1].strip()
            return after.splitlines()[0][:40] or "节点输出"
    return "节点输出"
