from __future__ import annotations

import os

from dotenv import load_dotenv

from novel_agent.graph import build_graph
from novel_agent.models import ModelConfig, build_model

load_dotenv()

dry_run = os.getenv("NOVEL_AGENT_DRY_RUN", "").lower() in {"1", "true", "yes"}
provider = os.getenv("LLM_PROVIDER", "openai")
model_name = os.getenv(
    "NOVEL_AGENT_MODEL",
    "deepseek-v4-flash" if provider.lower() == "deepseek" else "gpt-4.1-mini",
)

graph = build_graph(
    build_model(ModelConfig(model=model_name, dry_run=dry_run, provider=provider)),
    studio_input=True,
)
