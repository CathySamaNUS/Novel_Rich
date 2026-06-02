SYSTEM_RULES = """
你是一个商业类型小说写作工作流中的专业节点。
要求：
1. 输出必须具体，避免空泛建议。
2. 优先服务读者情绪、冲突升级、人物欲望和章节钩子。
3. 保持前后设定一致，不要随意改名、改关系、改时间线。
4. 中文输出。
""".strip()


def world_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：生成小说世界观和核心卖点设定。

题材：{state["idea"]}
类型：{state["genre"]}
文风：{state["style"]}
已有素材：{state["source_material"]}

请输出：
- 一句话卖点
- 故事底层冲突
- 世界/社会/家族规则
- 主角处境
- 主要爽点机制
- 禁忌和风险
- 适合反复使用的场景资产
""".strip()


def character_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：生成人物设定表。

题材：{state["idea"]}
世界观：{state["world_bible"]}
已有素材：{state["source_material"]}

请输出：
- 女主：外在身份、内在欲望、伤口、能力、误区、成长弧
- 男主/关键关系人：身份、欲望、秘密、与女主的拉扯
- 反派/阻力：利益诉求、压迫方式、弱点
- 配角：每个人的功能和隐藏变量
- 人物关系张力表
""".strip()


def outline_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：生成整本小说大纲。

题材：{state["idea"]}
类型：{state["genre"]}
世界观：{state["world_bible"]}
人物：{state["characters"]}
本次计划生成章节数：{state["max_chapters"]}
已有素材：{state["source_material"]}

请输出：
- 开篇钩子
- 三幕结构
- 每章一句话剧情
- 感情线/事业线/复仇线推进
- 伏笔与回收计划
- 结尾反转
""".strip()


def chapter_plan_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：规划第 {state["current_chapter"]} 章。

总大纲：{state["outline"]}
人物设定：{state["characters"]}
已有素材：{state["source_material"]}
已发生事件：{state["continuity_notes"]}
上一章摘要：{state["last_chapter_summary"]}

请输出：
- 本章目标
- 开场钩子
- 3-5 个场景 beat
- 情绪推进
- 冲突升级
- 结尾钩子
- 本章必须保持一致的设定
""".strip()


def draft_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：写第 {state["current_chapter"]} 章正文。

文风：{state["style"]}
世界观：{state["world_bible"]}
人物：{state["characters"]}
章节规划：{state["chapter_plan"]}
已发生事件：{state["continuity_notes"]}

写作要求：
- 直接写正文，不要解释创作思路。
- 有行动、对白、心理、场景细节。
- 保持强冲突和章节结尾钩子。
- 避免总结式流水账。
- 字数目标：{state["words_per_chapter"]} 字左右。
""".strip()


def critique_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：审校最新章节。

世界观：{state["world_bible"]}
人物：{state["characters"]}
章节规划：{state["chapter_plan"]}
最新章节：{state["drafts"][-1]}

请检查：
- 人物动机是否一致
- 情绪是否足够强
- 是否有新的矛盾或反转
- 是否有设定冲突
- 是否有水文、重复、解释过多
- 需要润色的具体位置
""".strip()


def revise_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：根据审校意见润色最新章节。

审校意见：{state["critique"]}
原章节：{state["drafts"][-1]}

要求：
- 保留原剧情方向。
- 增强冲突、对白拉扯、动作细节和结尾钩子。
- 修复设定不一致。
- 只输出润色后的章节正文。
""".strip()


def summarize_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：更新连续性记录。

最新章节：{state["drafts"][-1]}
旧连续性记录：{state["continuity_notes"]}

请输出：
- 本章发生的大事
- 人物关系变化
- 新增伏笔
- 已回收伏笔
- 下一章必须记住的信息
""".strip()
