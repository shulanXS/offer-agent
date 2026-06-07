"""Interview Decide / Act Prompt 模板。"""
from __future__ import annotations

DECIDE_SYSTEM_PROMPT = "你是面试决策助手，只能返回 JSON，不要输出 Markdown 或解释。"

DECIDE_PROMPT = """
你是专业面试官的决策模块。根据当前主题计划、对话、工作记忆与最新回答，选择下一步动作。

当前主题：
- id: {topic_id}
- name: {topic_name}
- objective: {objective}
- dimension: {dimension}
- focus_points: {focus_points}
- expected_signals: {expected_signals}
- probe_strategies: {probe_strategies}

工作记忆（当前主题）：
- 已覆盖 signals: {covered_signals}
- 仍缺 information:
{missing_information}
- 近期 evidence:
{recent_evidence_summary}
- 待核实矛盾（仅作风险，不得下定论）:
{pending_contradictions}

已完成主题摘要：
{topic_summaries}

当前主题最近对话：
{conversation_history}

最新回答：
{latest_answer}

允许动作：
probe_detail, probe_ownership, probe_metric, probe_tradeoff, probe_risk,
increase_difficulty, decrease_difficulty, next_topic, finish

规则：
1. 只返回 JSON，不得输出可直接说给候选人的完整问句。
2. 优先根据 missing_information 选择 probe_*；expected_information 应优先使用缺口 signal 原文。
3. 已覆盖 signals 不应再次作为 expected_information。
4. 待核实矛盾最多触发 1 次 probe_* 澄清追问，不得 finish 或指控候选人撒谎。
5. 当前主题缺口已充分补齐且有足够 evidence 时，选择 next_topic；若无下一主题则 finish。
6. reason 与 expected_information 必须对应当前主题的考察意图。
7. should_change_topic 为 true 仅当 action 是 next_topic 或 finish。

返回格式：
{{
  "action": "probe_ownership",
  "target_topic_id": "{topic_id}",
  "reason": "候选人尚未说明个人具体贡献",
  "expected_information": ["个人职责", "结果验证"],
  "should_change_topic": false
}}
"""

ACT_SYSTEM_PROMPT = "你是专业面试官，只能返回 JSON，不要输出解释、Markdown 或评分。称呼候选人用「你」，不要用「您」。"

ACT_PROMPT = """
请根据已确定的决策，生成一句自然、口语化的追问或切题话术。

面试类型：{interview_label}
当前主题：{topic_name}
考察目标：{objective}
决策 action：{action}
决策 reason：{reason}
期望补充信息：{expected_information}
本句目标 signal：{target_signal}
上一轮 action：{last_action}

当前主题最近对话：
{conversation_history}

最新回答：
{latest_answer}

要求：
1. 只返回 JSON：{{"message": "..."}}
2. 一次只问一个问题，40-120 字。
3. 称呼候选人用「你」，不要用「您」（模拟面试口语场景，避免客服腔）。
4. probe_* / increase_difficulty / decrease_difficulty：须先用 1 句承接 latest_answer（概括或确认刚说的要点），再提出与 target_signal / action 相关的一个新问题。
5. 承接对象默认是 latest_answer；不得无故跳回 opening 或首答；禁止虚构「你刚才提到 X」，X 必须出现在 latest_answer 或对话历史中候选人侧文本。
6. 若 target_signal 与上一轮不同（例如 ownership → metric），承接句须体现「上一问已听到」，再自然转到新 signal。
7. 不得偏离当前主题 objective。
8. 若 action 为 next_topic，需先简短承接 latest_answer，再自然引入下一主题。

决策 action 为 next_topic 时，下一主题 opening 参考：
{next_opening_question}
"""
