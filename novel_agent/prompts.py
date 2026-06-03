SYSTEM_RULES = """
你是商业网络小说工作流中的专业写作节点。

总原则：
1. 所有输出必须具体、可执行、能直接被后续节点使用。
2. 优先服务读者体验：情绪拉扯、利益冲突、关系变化、章节钩子。
3. 严格尊重既有设定，不要擅自改名、改关系、改时间线、改已经发生的事实。
4. 区分“长期稳定设定”和“随剧情变化的状态”。
5. 中文输出。
""".strip()


def world_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：为一部新小说生成长期稳定的世界观圣经。

小说设定：{state["idea"]}
类型：{state["genre"]}
文风：{state["style"]}

请输出：
- 核心卖点
- 故事底层冲突
- 世界/圈层/家族运行规则
- 主角初始处境
- 长期有效的主要爽点机制
- 高风险禁忌与不可碰的底线
- 可反复调用的场景资产

要求：
- 这些内容要尽量稳定，后续章节不应随意推翻。
""".strip()


def character_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：输出“长期稳定人物设定表”，只写不应轻易变化的内容。

小说设定：{state["idea"]}
世界观：{state["world_bible"]}

请输出：
- 女主：身份、核心欲望、核心伤口、长期能力、性格底色、成长方向
- 男主/关键关系人：身份、欲望、秘密、压迫感、与女主的长期张力
- 反派/阻力：利益诉求、惯用手段、弱点
- 配角：功能、立场、隐藏变量
- 人物关系底盘：谁和谁天然对立，谁和谁天然互相利用，谁会被谁吸引

要求：
- 这里写的是“人物圣经”，不要写容易随章节变化的临时状态。
""".strip()


def outline_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：为新小说生成可执行的大纲。

小说设定：{state["idea"]}
类型：{state["genre"]}
世界观：{state["world_bible"]}
人物圣经：{state["characters"]}
计划章节数：{state["max_chapters"]}

请输出：
- 开篇钩子
- 三幕结构或阶段推进
- 主线目标与阶段阻碍
- 每章一句话推进
- 感情线/事业线/复仇线或核心支线的推进方式
- 伏笔与回收计划
- 结尾反转方向
""".strip()


def bootstrap_character_state_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：建立“动态人物状态表”。

长期人物设定：{state["characters"]}
已有素材：{state["source_material"]}
连续性记录：{state["continuity_notes"]}
上一章摘要：{state["last_chapter_summary"]}

请输出当前时点的人物状态：
- 每个关键人物的当前身份位置
- 对外关系现状
- 对内真实欲望
- 已暴露秘密/未暴露秘密
- 当前站队与利益绑定
- 与上一阶段相比发生了什么变化

要求：
- 只写“当前状态”，不要重写整个人设。
""".strip()


def bootstrap_plot_memory_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：建立“剧情推进记忆”。

大纲：{state["outline"]}
已有素材：{state["source_material"]}
连续性记录：{state["continuity_notes"]}

请输出：
- 当前主线推进到哪里
- 正在发酵的支线
- 已埋下但未回收的伏笔
- 必须持续升级的冲突
- 时间线关键节点
- 下一章最值得承接的戏剧压力

要求：
- 只保留后续创作真正需要记住的推进信息。
""".strip()


def chapter_plan_prompt(state):
    feedback = _human_feedback_block(state)
    return f"""
{SYSTEM_RULES}

任务：规划第 {state["current_chapter"]} 章。

小说设定：{state["idea"]}
世界观圣经：{state["world_bible"]}
人物圣经：{state["characters"]}
动态人物状态：{state["character_state"]}
总体大纲：{state["outline"]}
剧情推进记忆：{state["plot_memory"]}
连续性记录：{state["continuity_notes"]}
上一章摘要：{state["last_chapter_summary"]}
{feedback}

请输出：
- 本章核心目标
- 本章必须推进的关系或利益变化
- 开场钩子
- 4-6 个场景 beat
- 每个 beat 的情绪与冲突功能
- 本章结尾钩子
- 本章绝不能写错的设定与事实

要求：
- 这是可直接拿来写正文的执行版章节卡。
""".strip()


def draft_prompt(state):
    feedback = _human_feedback_block(state)
    return f"""
{SYSTEM_RULES}

任务：写第 {state["current_chapter"]} 章正文。

文风：{state["style"]}
世界观圣经：{state["world_bible"]}
人物圣经：{state["characters"]}
动态人物状态：{state["character_state"]}
剧情推进记忆：{state["plot_memory"]}
章节规划：{state["current_chapter_plan"]}
连续性记录：{state["continuity_notes"]}
上一章摘要：{state["last_chapter_summary"]}
{feedback}

写作要求：
- 直接输出正文，不要解释创作思路。
- 让人物通过行动、对话、反应和选择暴露关系变化。
- 维持强冲突、强情绪和明确的章节推进。
- 避免重复解释、概述式流水账、空泛抒情。
- 严格延续人物称呼、关系、身份、时间线和伏笔状态。
- 字数目标：{state["words_per_chapter"]} 字左右。
""".strip()


def critique_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：像资深编辑一样审校最新章节。

人物圣经：{state["characters"]}
动态人物状态：{state["character_state"]}
剧情推进记忆：{state["plot_memory"]}
章节规划：{state["current_chapter_plan"]}
最新章节：{state["current_draft"]}

请按下面结构输出：
- 总评：一句话判断这一章是否成立
- 主要问题：列出最影响阅读体验的 3-5 个问题
- 具体修改建议：指出该删、该补、该加强的位置
- 是否需要重生成：是/否，并说明原因

重点检查：
- 人物动机与既有状态是否一致
- 情绪拉扯和利益冲突是否足够强
- 本章是否真的推进了剧情而不是原地打转
- 是否出现设定冲突、关系跳变、信息重复
- 结尾钩子是否足够让人继续读
""".strip()


def summarize_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：为已确认版本的第 {state["current_chapter"]} 章生成摘要和连续性记录条目。

已确认章节：{state["current_draft"]}
旧连续性记录：{state["continuity_notes"]}

请输出：
- 本章大事
- 关系变化
- 状态变化
- 新增伏笔
- 已回收伏笔
- 下一章必须记住的信息

要求：
- 简洁、可检索、便于后续写作调用。
""".strip()


def update_character_state_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：根据已确认章节，更新“动态人物状态表”。

长期人物设定：{state["characters"]}
旧动态人物状态：{state["character_state"]}
本章摘要：{state["last_chapter_summary"]}
本章正文：{state["current_draft"]}

请输出更新后的动态人物状态：
- 当前身份位置
- 外显关系变化
- 内在欲望变化
- 新暴露秘密/仍隐藏秘密
- 新的利益绑定或对立
- 下一章人物层面的危险点

要求：
- 不要改写人物底层设定，只更新剧情发展导致变化的部分。
""".strip()


def update_plot_memory_prompt(state):
    return f"""
{SYSTEM_RULES}

任务：根据已确认章节，更新“剧情推进记忆”。

总体大纲：{state["outline"]}
旧剧情推进记忆：{state["plot_memory"]}
本章摘要：{state["last_chapter_summary"]}
本章正文：{state["current_draft"]}

请输出更新后的剧情推进记忆：
- 主线目前推进到哪里
- 新增或升级的支线
- 尚未回收的伏笔
- 已被兑现的承诺或反转
- 当前时间线位置
- 下一章最优先承接的戏剧压力

要求：
- 只保留写下一章真正需要的信息。
""".strip()


def _human_feedback_block(state):
    feedback = (state.get("current_human_feedback") or "").strip()
    if not feedback:
        return "本轮无额外人工反馈。"
    return f"本轮人工反馈：{feedback}"
