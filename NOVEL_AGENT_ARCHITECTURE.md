# Novel Agent Architecture

## 目标

这份文档用于固定当前小说 agent 的整体框架，方便：

- 快速理解系统现在怎么跑
- 明确 `new` 和 `continue` 两种模式的差别
- 记录关键记忆层和人工审阅机制
- 后续改功能时，知道要同步改哪些模块
- 作为功能变更回顾文档持续维护

## 当前定位

这是一个基于 LangGraph 的小说工作流，核心目标不是“一次性生成整本书”，而是：

- 支持从零创建新小说
- 支持读取已有内容继续续写
- 每章生成后先经过审校，再由作者决定是否保存
- 通过分层记忆保持长期设定稳定，同时允许剧情状态动态变化
- 可选把“写法策略”独立成 `writing_skill.md`，让写作规则可以单独优化

## 两种运行模式

### `new`

适用场景：

- 只有一个新的小说创意
- 还没有现成章节、人设、剧情资料

流程：

1. 生成 `world_bible`
2. 生成 `characters`
3. 生成 `outline`
4. 建立初始 `character_state`
5. 建立初始 `plot_memory`
6. 进入逐章生成

### `continue`

适用场景：

- 已经有现成小说资料，要基于现有内容续写

流程：

1. 从 `source_dir` 读取已有资料
2. 如果已有 `character_state.md` 和 `plot_memory.md`，直接进入逐章续写
3. 如果没有，就先从旧文自动补建，再进入逐章续写

## 输入层

当前支持的主要输入字段：

- `idea`：小说核心创意。`continue` 模式可以留空，默认取 `source_dir` 目录名。
- `genre`：类型标签
- `style`：文风要求
- `mode`：`new` 或 `continue`
- `source_dir`：已有小说目录，仅 `continue` 必填
- `writing_skill`：可选，直接传入覆盖默认写作 skill
- `enable_writing_skill`：是否启用独立 writing skill 机制，默认关闭
- `max_chapters`：本次最多生成几章
- `words_per_chapter`：每章目标字数
- `review_required`：是否开启人工审阅
- `auto_approve`：是否自动通过审阅

对应实现位置：

- `novel_agent/state.py`
- `run.py`

## 记忆分层

这是当前最重要的设计。系统不再把所有记忆混成一个文本块，而是拆成几层。

### 1. `world_bible.md`

含义：

- 世界规则
- 圈层规则
- 家族/社会运行逻辑
- 长期卖点和底层冲突

特征：

- 长期稳定
- 不应被章节推进轻易改写

### 2. `characters.md`

含义：

- 人物圣经
- 稳定身份
- 核心欲望
- 核心伤口
- 长期能力和成长方向

特征：

- 长期稳定
- 不直接记录临时剧情状态

### 3. `character_state.md`

含义：

- 当前人物身份位置
- 当前站队
- 当前关系变化
- 当前利益绑定
- 已暴露/未暴露秘密

特征：

- 动态更新
- 每章确认后更新一次

### 4. `outline.md`

含义：

- 整体剧情路线
- 阶段推进
- 每章一句话推进
- 伏笔与回收方向

特征：

- 相对稳定
- 允许后续在大方向内迭代，但不是每章都重建

### 5. `plot_memory.md`

含义：

- 主线推进到哪里
- 哪些支线在发酵
- 哪些伏笔未回收
- 下一章最该承接的戏剧压力

特征：

- 动态更新
- 每章确认后更新一次

### 6. `continuity_notes.md`

含义：

- 按章追加的连续性记录

特征：

- 不是覆盖式更新，而是追加式
- 便于追溯发生过什么

### 7. `last_chapter_summary.md`

含义：

- 最新一章的摘要

特征：

- 主要服务下一章规划和承接

### 8. `writing_skill.md`

含义：

- 独立的章节写法规则
- 场景推进、关系拉扯、钩子、语言控制等执行准则

特征：

- 不属于世界观或人物设定
- 可以单独迭代优化
- 只有显式开启后才参与工作流
- `continue` 模式开启后优先读取已有 skill，便于长期调教同一部小说的写法

## 当前图结构

### 新小说模式主链路

`load_source_material -> build_world -> build_characters -> build_outline -> bootstrap_character_state -> bootstrap_plot_memory -> plan_chapter -> write_chapter -> critique_chapter -> condense_regenerate_brief -> human_review -> summarize_chapter -> update_character_state -> update_plot_memory -> finalize_chapter`

### 续写模式主链路

`load_source_material -> (已有动态记忆则直接 plan_chapter；否则先 bootstrap_character_state / bootstrap_plot_memory) -> 逐章生成链`

### 人工审阅分支

在 `human_review` 节点，作者有三种选择：

- `approve`：确认当前章节，写入正式输出，并更新所有记忆
- `regenerate`：基于反馈先重做章节规划，再重生成当前章节
- `edit`：作者直接修改正文，修改后版本作为正式版本保存

## 章节级工作流

每章现在按这个顺序处理：

1. `plan_chapter`
2. `write_chapter`
3. `critique_chapter`
4. `condense_regenerate_brief`
5. `human_review`
6. `summarize_chapter`
7. `update_character_state`
8. `update_plot_memory`
9. `finalize_chapter`

其中第 4 步是当前新增的重要能力：

- 把长篇 `critique` 压缩成可直接拿去重生成的简明反馈
- 作者可以直接采用，也可以修改后再用

## 审阅与重生成机制

### 旧问题

原先的问题是：

- 审校报告太长
- 作者需要自己从报告里提炼“到底该怎么重生成”
- 容易把建议写散，导致下一轮模型抓不住重点

### 当前方案

在 `critique_chapter` 之后增加一层：

- `condense_regenerate_brief`

它会把审校意见压成四部分：

- 保留项
- 必改项
- 强化项
- 禁止项

这样作者在 `regenerate` 时：

- 可以直接采用这份建议
- 也可以在此基础上小改
- 不需要每次从头整理审校报告
- 工作流会先回到 `plan_chapter`，重做本章章节卡，再进入 `write_chapter`
- 新提示词会显式看到上一版正文、审校要点和重生成 brief，减少“只换说法不换打法”的弱重写

## 输出文件结构

每个项目目录下现在会输出：

- `world_bible.md`
- `characters.md`
- `character_state.md`
- `outline.md`
- `plot_memory.md`
- `continuity_notes.md`
- `last_chapter_summary.md`
- `writing_skill.md`
- `chapters/*.md`
- `plans/*.md`
- `reviews/*.md`
- `summaries/*.md`
- `full_draft.md`

## 关键代码位置

### `novel_agent/state.py`

职责：

- 定义输入结构
- 定义运行态 state
- 定义默认值

改这里的典型场景：

- 新增状态字段
- 修改默认题材/默认文风
- 新增输入参数

### `novel_agent/prompts.py`

职责：

- 所有节点提示词

改这里的典型场景：

- 调整世界观生成风格
- 调整人物圣经结构
- 调整审校维度
- 调整重生成 brief 的压缩格式

### `novel_agent/graph.py`

职责：

- 定义 LangGraph 节点
- 定义节点间路由
- 定义中断式人工审阅

改这里的典型场景：

- 新增一个节点
- 调整节点顺序
- 增加 `interrupt` 审阅逻辑
- 修改 `new/continue` 分流

### `novel_agent/output.py`

职责：

- 把最终确认后的结果落盘

改这里的典型场景：

- 增加新输出文件
- 修改章节编号策略
- 调整目录结构

### `run.py`

职责：

- CLI 入口
- 命令行参数
- CLI 下的人工审阅交互

改这里的典型场景：

- 增加命令行参数
- 调整 CLI 交互文案
- 增加新的快捷模式

### `README.md`

职责：

- 面向使用者的说明

改这里的典型场景：

- 功能变更后同步更新使用方法
- 更新 `new/continue` 示例

## 修改一个功能时，通常要同步检查哪些地方

### 如果改“状态结构”

至少检查：

- `novel_agent/state.py`
- `novel_agent/graph.py`
- `novel_agent/output.py`
- `README.md`

### 如果改“提示词逻辑”

至少检查：

- `novel_agent/prompts.py`
- `novel_agent/graph.py`
- 必要时更新 `README.md`

### 如果改“人工审阅机制”

至少检查：

- `novel_agent/graph.py`
- `run.py`
- `README.md`

### 如果改“续写读取逻辑”

至少检查：

- `novel_agent/graph.py`
- `novel_agent/state.py`
- `README.md`

## 当前已完成的重要改造

### 第一阶段

- 去掉了与仓库现有故事不匹配的默认示例
- 把默认题材调整为当前“酒店家族/财阀圈”方向

### 第二阶段

- 增加人工审阅中断节点
- 支持 `approve / regenerate / edit`
- 支持 CLI 审阅交互

### 第三阶段

- 把记忆拆成长期设定层和动态状态层
- 增加 `character_state.md`
- 增加 `plot_memory.md`
- 章节确认后自动更新动态记忆

### 第四阶段

- 增加审校报告压缩能力
- 可以把 `critique` 自动整理成适合重生成的短反馈

## 变更日志

### 2026-06-04

改动主题：补充总览架构文档，建立后续回顾基线。

本次新增：

- 新建 `NOVEL_AGENT_ARCHITECTURE.md`
- 汇总 `new / continue` 双模式
- 固定当前记忆分层设计
- 固定章节级工作流与人工审阅机制
- 固定关键模块职责和联动修改点

改动原因：

- 当前 agent 已经从简单线性生成，演进到分层记忆 + 人工审阅 + 续写双模式
- 如果不单独维护总览文档，后续功能增加后会很难快速判断应该改哪个模块
- 需要一个适合作为“架构索引 + 功能回顾”的固定入口

影响模块：

- 新增文档，不影响运行逻辑

用户使用变化：

- 无运行时变化
- 增加了一份长期维护文档，后续应与 README 一起维护

### 2026-06-04 Skill 外置化

改动主题：把写作规则独立成可持续优化的 `writing_skill.md`。

本次新增：

- 新增 `novel_agent/writing_skill.py`，提供默认写作 skill 模板
- 运行态 state 新增 `writing_skill` 字段
- `continue` 模式支持从已有项目读取 `writing_skill.md / skill.md / 写作技能.md`
- 输出目录新增 `writing_skill.md`
- `plan / draft / critique / regenerate_brief` 全部接入写作 skill

改动原因：

- 现在的写法规则散落在 prompt 里，不利于单独调优
- 如果后续要借鉴 SkillOpt 思路，首先要把“可训练对象”从大 prompt 中拆出来
- 独立 skill 文档后，后续才适合做版本比较、失败归因和 gated 更新

影响模块：

- `novel_agent/state.py`
- `novel_agent/graph.py`
- `novel_agent/prompts.py`
- `novel_agent/output.py`
- `README.md`
- `NOVEL_AGENT_ARCHITECTURE.md`

用户使用变化：

- 默认不开启，不影响原有 agent 写作链路
- 开启后新项目会自动产出 `writing_skill.md`
- 旧项目只要补上这个文件，续写时也能直接沿用
- 如不提供，系统会回退到默认写作 skill

### 2026-06-04 Skill 演化 Gate

改动主题：把 SkillOpt 风格的 skill 更新做成“问题触发 + 人工 gate”的低风险链路。

本次新增：

- 新增 `enable_skill_evolution` 开关
- 章节确认后，只有在审校明确需要重生成或出现人工重生成反馈时，才进入 skill reflection
- 新增 `skill_update_review` 中断，作者可选择 `apply / edit / skip`
- 新增 `skill_updates.md`，记录被采纳的 skill 补丁历史

改动原因：

- 不能把每章波动都写进长期 skill，否则很快会把 skill 文档污染掉
- SkillOpt 的核心不是“自动乱改”，而是把可泛化规则当作稀缺更新对象，并加 gate 控制
- 先做成保守触发，才适合在真实写作流程里长期使用

影响模块：

- `novel_agent/graph.py`
- `novel_agent/prompts.py`
- `novel_agent/models.py`
- `novel_agent/output.py`
- `run.py`
- `README.md`
- `NOVEL_AGENT_ARCHITECTURE.md`

用户使用变化：

- 只开 `--enable-writing-skill` 时，不会自动演化 skill
- 开 `--enable-skill-evolution` 后，也不是每章都触发更新
- 真正触发时，仍然由你最终决定是否把补丁写入长期 skill

### 2026-06-04 Skill 开关化

改动主题：为 writing skill 外置层增加显式开关，默认不介入原有工作流。

本次新增：

- 运行态 state 新增 `enable_writing_skill`
- CLI 新增 `--enable-writing-skill`
- 关闭时不读取、不注入、不输出 `writing_skill.md`
- 开启时才加载和输出 skill 文档

改动原因：

- 你当前最重要的是保住已有小说 agent 的可用链路
- skill 外置化是增强项，不应该默认侵入原工作流
- 先做成显式开关，后续才适合逐步灰度启用和比较效果

影响模块：

- `novel_agent/state.py`
- `novel_agent/graph.py`
- `novel_agent/prompts.py`
- `novel_agent/output.py`
- `run.py`
- `README.md`
- `NOVEL_AGENT_ARCHITECTURE.md`

用户使用变化：

- 默认运行时与改造前保持一致
- 只有显式加 `--enable-writing-skill`，skill 外置层才会生效

### 2026-06-04 之前已完成的功能改造汇总

改动主题：把原始小说生成脚本升级为可长期维护的小说 agent。

关键改造：

- 修正默认示例和默认题材，使其与仓库现有小说素材一致
- 增加 `continue` 模式，从已有目录读取资料后续写
- 增加长期人设层 `characters.md`
- 增加动态人物状态层 `character_state.md`
- 增加剧情推进记忆层 `plot_memory.md`
- 把 `continuity_notes.md` 改成按章追加，避免旧事实被覆盖
- 加入人工审阅节点，支持 `approve / regenerate / edit`
- CLI 增加交互式审阅输入
- 审校后新增重生成 brief 压缩层，减少作者自己整理反馈的成本

影响模块：

- `novel_agent/state.py`
- `novel_agent/prompts.py`
- `novel_agent/graph.py`
- `novel_agent/output.py`
- `run.py`
- `README.md`

用户使用变化：

- 续写时需要提供 `source_dir`
- 默认会在每章后进入人工审阅
- 重生成时可以直接使用系统压缩好的建议

## 后续建议

下一步比较值得做的增强有：

- 增加“章节评分表”结构化输出，方便比较多个重生成版本
- 增加“保留旧版本草稿”的机制，便于回退
- 增加“人物状态变更 diff”输出，方便追踪角色变化
- 增加“主线/感情线/事业线推进仪表盘”

## 文档维护规则

以后每次改 agent，建议同步更新这份文档，最少改两处：

1. 改动涉及的架构部分
2. `当前已完成的重要改造` 区域

如果改动比较大，直接新增一个小节，记录：

- 改了什么
- 为什么改
- 影响哪些模块
- 用户使用方式有没有变化


### 2026-06-04 Batch Skill 触发与双层 Skill 拆分

改动主题：把写作 skill 拆成通用层和小说层，并把 skill 演化改成 batch 级触发。

本次新增：

- `shared_writing_skill` 与 `novel_writing_skill` 双层 skill 结构
- prompt 使用时把两层 skill 组合注入
- skill 演化只更新 `novel_writing_skill`，不改通用 skill
- 新增 `skill_evolution_window` 与 `skill_failure_threshold`
- 累积满 2 章且出现 2 次高失败后，才触发一次小说特定 skill 更新审核

改动原因：

- 小说通用写法规则和单本小说特定写法规则本来就不应混在一起
- 单章字数大、信息密度高，逐章立即改 skill 太敏感，batch 级触发更稳
- 只有重复失败模式才值得固化成小说长期规则

影响模块：

- `novel_agent/state.py`
- `novel_agent/writing_skill.py`
- `novel_agent/prompts.py`
- `novel_agent/graph.py`
- `novel_agent/output.py`
- `run.py`
- `README.md`

用户使用变化：

- 现在写作 skill 默认分成通用层和小说层
- 开启 skill 演化后，不会每章都尝试改 skill
- 真正触发更新时，只会修改小说层 skill，通用层保持稳定
