# Novel Agent

基于 LangGraph 的自动写小说工作流。它把写作拆成多个节点：世界观、人物、小纲、章节规划、正文、审校、润色、状态更新，并用条件边循环生成多章。

## 安装

```bash
cd /Users/cathy/Documents/Novel/novel_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 先用 dry-run 验证流程

```bash
python run.py --dry-run --idea "穿越恶毒女配嫁入财阀家族后反向改命" --max-chapters 2
```

## 使用 DeepSeek 真实生成

在 `.env` 里配置：

```bash
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的 DeepSeek key
DEEPSEEK_BASE_URL=https://api.deepseek.com
NOVEL_AGENT_MODEL=deepseek-v4-flash
```

DeepSeek 官方 OpenAI-compatible base URL 是 `https://api.deepseek.com`，常用模型包括 `deepseek-v4-flash` 和 `deepseek-v4-pro`。

运行：

```bash
python run.py \
  --provider deepseek \
  --model deepseek-v4-flash \
  --idea "穿越恶毒女配嫁入财阀家族后反向改命" \
  --genre "女频、财阀、穿越、爽文" \
  --style "强情绪、快节奏、反转密集、对白有拉扯" \
  --max-chapters 3
```

## 使用 OpenAI 真实生成

```bash
export OPENAI_API_KEY="你的 key"
python run.py \
  --idea "穿越恶毒女配嫁入财阀家族后反向改命" \
  --genre "女频、财阀、穿越、爽文" \
  --style "强情绪、快节奏、反转密集、对白有拉扯" \
  --max-chapters 3
```

生成结果会写到：

```text
output/<项目名>/
```

包括 `world_bible.md`、`characters.md`、`outline.md`、每章正文、审校意见和 `full_draft.md`。
