"""Interview Evidence Extraction Prompt。"""
from __future__ import annotations

EVIDENCE_SYSTEM_PROMPT = "你是面试证据提取助手，只能返回 JSON，不要输出 Markdown 或解释。"

EVIDENCE_PROMPT = """
从候选人最新回答中提取结构化证据，用于后续追问与评估。

当前主题：
- id: {topic_id}
- name: {topic_name}
- objective: {objective}
- dimension: {dimension}
- expected_signals: {expected_signals}
- focus_points: {focus_points}

已完成主题摘要：
{topic_summaries}

当前主题最近对话：
{conversation_history}

最新回答：
{latest_answer}

已有工作记忆（摘要）：
- claims 数量: {existing_claim_count}
- evidence 数量: {existing_evidence_count}

规则：
1. 只返回 JSON，不得输出可直接说给候选人的完整问句。
2. evidence.quote 必须是 latest_answer 中的原话短句，不得编造。
3. evidence.matched_signal 与 missing_information.signal 必须来自 expected_signals 或 focus_points 原文。
4. evidence.polarity 只能是 positive / negative / neutral。
5. claims.probe_hint 只能是 probe_detail / probe_ownership / probe_metric / probe_tradeoff / probe_risk / increase_difficulty / decrease_difficulty 之一，或省略。
6. potential_contradictions 只记录待验证风险，不得下定论。

返回格式：
{{
  "answer_quality": "weak|partial|strong",
  "claims": [
    {{
      "topic_id": "{topic_id}",
      "content": "负责订单服务架构设计",
      "status": "unverified",
      "probe_hint": "probe_ownership"
    }}
  ],
  "evidence": [
    {{
      "topic_id": "{topic_id}",
      "matched_signal": "个人贡献",
      "polarity": "positive",
      "quote": "我负责订单服务拆分和迁移",
      "strength": 0.7,
      "rationale": "说明了个人负责范围"
    }}
  ],
  "missing_information": [
    {{
      "topic_id": "{topic_id}",
      "signal": "结果指标",
      "from_plan": true
    }}
  ],
  "risks": [],
  "potential_contradictions": []
}}
"""
