# Novel Agent

基于 LangGraph 的小说工作流，支持两种入口：

- `new`：只给一个新小说设定，从零生成世界观、人物圣经、大纲，再进入逐章写作。
- `continue`：读取已有小说目录，接着现有章节往后续写。

这一版重点解决了三个核心问题：

- 例子和默认设定已经改成和仓库现有的“酒店家族/财阀圈”素材一致，不再混入不匹配的默认题材。
- 增加了人工审阅节点：每章生成后先审校，再由你决定 `approve`、`regenerate` 或 `edit`，确认前不会入库。
- 把记忆拆成三层：`characters.md` 负责长期稳定人设，`character_state.md` 负责随剧情变化的人物状态，`plot_memory.md` 负责剧情推进记忆。

## 安装

```bash
cd /Users/yuchengfang/Code/Novel_Rich
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 工作流结构

每一章现在是这条链路：

`章节规划 -> 正文生成 -> 编辑审校 -> 人工确认 -> 摘要更新 -> 人物状态更新 -> 剧情记忆更新`

其中：

- `world_bible.md`：长期稳定的世界规则、卖点、底层冲突。
- `characters.md`：长期稳定的人物圣经，不轻易变化。
- `character_state.md`：当前时点的人物身份、站队、关系、欲望变化。
- `plot_memory.md`：主线推进、支线发酵、伏笔回收、下一章压力。
- `continuity_notes.md`：按章追加的连续性记录。

## 新建一本小说

最简单：

```bash
python run.py \
  --idea "华裔酒店家族千金回国接手国内业务，却被卷入财阀圈合作与情感博弈" \
  --max-chapters 3
```

如果只是测试流程：

```bash
python run.py \
  --dry-run \
  --max-chapters 1 \
  --skip-review \
  --output output_new_test
```

## 续写已有小说

`continue` 模式会优先读取这些文件：

- `world_bible.md` 或 `世界观设定.md`
- `characters.md` 或 `人物设定.md`
- `outline.md` 或 `SUMMARY.md`
- `continuity_notes.md`
- `last_chapter_summary.md`
- `character_state.md`
- `plot_memory.md`
- `chapters/*.md`

如果 `character_state.md` 或 `plot_memory.md` 还不存在，工作流会先基于旧文自动补建，再开始续写。

示例：

```bash
python run.py \
  --mode continue \
  --source-dir "novel/狗血财阀文" \
  --max-chapters 2
```

## 人工审阅

CLI 默认开启人工审阅。每章生成后，你会看到：

- 章节规划
- 正文草稿
- 审校意见

然后你可以选择：

- `approve`：确认保存，并更新所有记忆文件。
- `regenerate`：输入反馈，重新生成这一章。
- `edit`：直接贴入你改好的完整正文，保存这个版本。

如果你要批量跑流程：

```bash
python run.py --dry-run --auto-approve --max-chapters 2
```

或者完全跳过审阅节点：

```bash
python run.py --skip-review --max-chapters 2
```

## 输出结构

结果会写到：

```text
output/<项目名>/
```

包括：

- `world_bible.md`
- `characters.md`
- `character_state.md`
- `outline.md`
- `plot_memory.md`
- `continuity_notes.md`
- `last_chapter_summary.md`
- `chapters/*.md`
- `plans/*.md`
- `reviews/*.md`
- `summaries/*.md`
- `full_draft.md`

## 模型配置

OpenAI：

```bash
export OPENAI_API_KEY="你的 key"
python run.py --max-chapters 2
```

DeepSeek：

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY="你的 key"
export DEEPSEEK_BASE_URL=https://api.deepseek.com
export NOVEL_AGENT_MODEL=deepseek-v4-flash

python run.py --provider deepseek --model deepseek-v4-flash --max-chapters 2
```
