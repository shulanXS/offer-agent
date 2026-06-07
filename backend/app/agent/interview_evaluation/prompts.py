"""Evaluation Agent Prompt（候选人可读报告）。"""
from __future__ import annotations

import json
from typing import Any


EVALUATION_SYSTEM_PROMPT = """你是专业模拟面试的反馈助手，面向候选人撰写易懂、具体、可执行的面试反馈。
只能基于输入中的证据与 plan 主题写作，禁止编造候选人未说过的话，禁止输出录用/拒绝结论。
分数与 verified 状态已由系统给出，你可以引用但不要自行修改。
亮点要克制、有证据，禁止空泛恭维（如「表现优秀」「非常棒」）；没有足够正面证据时 highlights 可返回空数组。
无明确表现问题时 weaknesses 与 suggestions 应返回空数组，禁止为凑条数编造问题；未聊主题属于覆盖度问题，不要写进 weaknesses。
输出必须是 JSON 对象。"""


def build_evaluation_prompt(*, evaluation_context: dict[str, Any], competencies: list[dict[str, Any]]) -> str:
    configuration = evaluation_context.get("configuration") or {}
    interview_type = configuration.get("interview_type", "experienced")
    audience = "校招" if interview_type == "campus" else "社招"

    compact_competencies = [
        {
            "topic_id": item["topic_id"],
            "name": item["name"],
            "dimension": item["dimension"],
            "status": item["status"],
            "score": item.get("score"),
            "evidence_references": item.get("evidence_references") or [],
            "strengths": item.get("strengths") or [],
            "risks": item.get("risks") or [],
        }
        for item in competencies
    ]
    scored_topic_count = sum(1 for item in competencies if item.get("score") is not None)
    total_topic_count = len(competencies)

    payload = {
        "interview_type": audience,
        "competencies": compact_competencies,
        "score_coverage": {
            "scored_topic_count": scored_topic_count,
            "total_topic_count": total_topic_count,
            "is_partial": scored_topic_count < total_topic_count if total_topic_count else False,
        },
        "risks": evaluation_context.get("risks") or [],
        "unverified_items": evaluation_context.get("unverified_items") or [],
    }

    return f"""请基于以下输入，生成面向候选人的{audience}模拟面试反馈文案。

要求：
1. 只输出 JSON，包含 candidate_review 与 competency_narratives。
2. candidate_review 字段：
   - headline：一句话总评（15-30 字，候选人能直接读懂）
   - summary：120-220 字，说明面得怎样、亮点与主要问题
   - highlights：0-3 条，每项为 {{"title": "...", "body": "..."}}；title 8-16 字，概括亮点主题（优先用考察方向名）；body 40-120 字，基于 positive evidence 引用原话或事实；语气克制；无证据则 []
   - weaknesses：0-4 条，每项为 {{"title": "...", "body": "..."}}；title 用考察方向名或问题类型（如「表述一致性」）；body 写已讨论主题中的真实不足；无明确问题时返回 []
   - suggestions：0-4 条，每项为 {{"title": "...", "body": "..."}}；title 用练习主题或改进方向；body 写可执行改进动作；无明确问题时返回 []
3. competency_narratives 每项包含 topic_id、evaluation_comment（40-120 字，像面试官点评，不要堆术语）
4. 未验证主题不要判低分，可写“讨论不足/证据不够”
5. 若输入 score_coverage.is_partial 为 true：不要说“整场面试/整体表现”，应写“已讨论的考察点”；不要暗示未聊主题表现差
6. 必须引用 evidence_references.quote 或 risks 中的事实，不要空泛

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}

输出 JSON 示例：
{{
  "candidate_review": {{
    "headline": "已讨论的考察点表现较好，表达比较清楚",
    "summary": "...",
    "highlights": [
      {{"title": "项目深挖", "body": "你提到「...」，对个人负责范围讲得比较清楚。"}}
    ],
    "weaknesses": [],
    "suggestions": []
  }},
  "competency_narratives": [
    {{"topic_id": "topic-1", "evaluation_comment": "..."}}
  ]
}}"""
