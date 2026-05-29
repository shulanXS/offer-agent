import logging
from copy import deepcopy
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.logging_utils import log_payload
from app.llm.factory import MockLLMClient, _looks_like_prompt_template, create_llm_client, extract_spoken_message


logger = logging.getLogger("uvicorn.error")

_SPOKEN_JSON_SYSTEM_PROMPT = "你是结构化输出助手，只能返回 JSON，不要输出解释、示例或 Markdown。"


def _spoken_message_from_llm(
    client: Any,
    *,
    prompt: str,
    operation_name: str,
    trace_id: str,
    fallback: str,
) -> str:
    try:
        payload = client.generate_json(
            prompt,
            _SPOKEN_JSON_SYSTEM_PROMPT,
            operation_name=operation_name,
            trace_id=trace_id,
        )
    except Exception:
        logger.exception(
            "[trace_id=%s] %s JSON parse failed, using rule fallback",
            trace_id or "-",
            operation_name,
        )
        return fallback

    text = extract_spoken_message(payload)
    if text:
        return text

    logger.warning(
        "[trace_id=%s] %s returned invalid spoken payload, using rule fallback",
        trace_id or "-",
        operation_name,
    )
    return fallback


class InterviewQuestion(TypedDict):
    id: str
    title: str
    prompt: str
    focus: str
    follow_up_hint: str


class ThreadMessage(TypedDict):
    role: Literal["assistant", "user"]
    kind: str
    content: str


class QuestionThread(TypedDict):
    question_id: str
    title: str
    focus: str
    follow_up_done: bool
    messages: list[ThreadMessage]


class PlanState(TypedDict, total=False):
    trace_id: str
    language: str
    difficulty_level: str
    job_title: str
    target_role: str
    resume_text: str
    highlights: list[str]
    work_experience: list[dict[str, str]]
    project_experience: list[dict[str, str]]
    technical_skills: list[str]
    planning_rag_context: str
    planning_rag_focus_points: list[str]
    planning_rag_sources: list[dict[str, Any]]
    model_provider: str
    model_name: str
    focus_points: list[str]
    questions: list[InterviewQuestion]
    current_question: InterviewQuestion
    initial_message: str
    session_title: str


class InterviewState(TypedDict, total=False):
    trace_id: str
    questions: list[InterviewQuestion]
    question_threads: list[QuestionThread]
    current_index: int
    answer: str
    assistant_message: str
    assistant_kind: str
    status: str
    target_role: str
    language: str
    difficulty_level: str
    model_provider: str
    model_name: str


class EvaluationState(TypedDict, total=False):
    trace_id: str
    target_role: str
    question_threads: list[QuestionThread]
    model_provider: str
    model_name: str
    result: dict[str, Any]


KNOWN_SKILLS = [
    "Python",
    "Java",
    "Go",
    "SQL",
    "Redis",
    "微服务",
    "接口设计",
    "测试",
    "性能优化",
    "AI",
    "LLM",
    "数据分析",
]


def extract_focus_points(resume_text: str, highlights: list[str]) -> list[str]:
    content = f"{resume_text}\n{' '.join(highlights)}".lower()
    discovered: list[str] = []
    for item in KNOWN_SKILLS:
        if item.lower() in content and item not in discovered:
            discovered.append(item)
    for highlight in highlights:
        cleaned = highlight.strip()
        if cleaned and cleaned not in discovered:
            discovered.append(cleaned)
    return discovered[:4] or ["项目表达", "技术取舍", "问题排查", "业务理解"]


def merge_focus_points(*focus_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for focus_group in focus_groups:
        for item in focus_group:
            cleaned = str(item).strip()
            if cleaned and cleaned not in merged:
                merged.append(cleaned)
            if len(merged) >= 4:
                return merged
    return merged


def build_questions(target_role: str, focus_points: list[str]) -> list[InterviewQuestion]:
    role = target_role or "后端开发工程师"
    focus = focus_points + ["技术取舍", "稳定性"]
    unique_focus: list[str] = []
    for item in focus:
        if item not in unique_focus:
            unique_focus.append(item)
    selected = unique_focus[:4]
    return [
        {
            "id": "q1",
            "title": "项目背景与职责",
            "prompt": "我们先从项目开始。请挑一个你最能代表自己的经历，用 STAR 或时间线方式讲清楚项目背景、你的职责，以及它为什么重要。",
            "focus": selected[0],
            "follow_up_hint": "继续追问候选人的个人贡献、指标变化和取舍依据。",
        },
        {
            "id": "q2",
            "title": f"{role} 的技术决策",
            "prompt": f"如果把这段经历放到 {role} 的真实工作场景里，你做过或会怎么做一次关键技术决策？请说明方案权衡和最终判断。",
            "focus": selected[1] if len(selected) > 1 else "技术取舍",
            "follow_up_hint": "继续追问备选方案、约束条件和验证方式。",
        },
        {
            "id": "q3",
            "title": "复杂问题排查",
            "prompt": "说一个你真的排查过的复杂问题，可以是性能、稳定性、线上故障或协作卡点。你是怎么定位、怎么收敛、最后怎样复盘的？",
            "focus": selected[2] if len(selected) > 2 else "问题排查",
            "follow_up_hint": "继续追问诊断步骤、证据链和复盘动作。",
        },
        {
            "id": "q4",
            "title": "业务与成长",
            "prompt": "最后讲讲，如果你重新做一次这段经历，你最想优化哪一部分？可以从业务结果、工程质量、协作效率三个维度展开。",
            "focus": selected[3] if len(selected) > 3 else "业务理解",
            "follow_up_hint": "继续追问改进优先级、预期收益和个人成长。",
        },
    ]


def adapt_question_difficulty(questions: list[InterviewQuestion], difficulty_level: str) -> list[InterviewQuestion]:
    if difficulty_level == "入门":
        prefix = "请结合一个最熟悉的场景，"
    elif difficulty_level == "进阶":
        prefix = "请补充你的判断依据，"
    elif difficulty_level == "挑战":
        prefix = "请把问题放到高压或线上场景里，"
    else:
        return questions
    adjusted: list[InterviewQuestion] = []
    for item in questions:
        updated = deepcopy(item)
        updated["prompt"] = f"{prefix}{item['prompt']}"
        adjusted.append(updated)
    return adjusted


def _format_experience(items: list[dict[str, str]]) -> str:
    if not items:
        return "暂无"
    return "\n".join(
        f"- {item.get('name', '经历')}: {item.get('detail', '').strip()}" for item in items if item.get("detail")
    ) or "暂无"


def _format_threads(threads: list[QuestionThread]) -> str:
    sections: list[str] = []
    for index, thread in enumerate(threads, start=1):
        lines = [f"第 {index} 题 - {thread.get('title', '')} / 焦点: {thread.get('focus', '')}"]
        for message in thread.get("messages", []):
            speaker = "面试官" if message.get("role") == "assistant" else "候选人"
            lines.append(f"{speaker}: {message.get('content', '')}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def _to_clean_string_list(value: Any, *, limit: int) -> list[str]:
    if isinstance(value, str):
        items = [segment.strip() for segment in value.split(",")]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value]
    else:
        return []
    result: list[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def _normalize_question_item(item: Any, *, index: int, focus_points: list[str]) -> InterviewQuestion | None:
    fallback_focus = focus_points[index - 1] if index - 1 < len(focus_points) else "综合能力"
    if isinstance(item, dict):
        prompt_text = str(item.get("prompt", "")).strip()
        if not prompt_text:
            return None
        return {
            "id": str(item.get("id") or f"q{index}"),
            "title": str(item.get("title") or f"题目 {index}"),
            "prompt": prompt_text,
            "focus": str(item.get("focus") or fallback_focus),
            "follow_up_hint": str(item.get("follow_up_hint") or "继续深挖候选人的个人贡献和判断依据。"),
        }
    if isinstance(item, str):
        prompt_text = item.strip()
        if not prompt_text:
            return None
        return {
            "id": f"q{index}",
            "title": f"题目 {index}",
            "prompt": prompt_text,
            "focus": fallback_focus,
            "follow_up_hint": "继续深挖候选人的个人贡献和判断依据。",
        }
    if isinstance(item, list):
        candidate_prompt = next((str(value).strip() for value in item if str(value).strip()), "")
        if not candidate_prompt:
            return None
        return {
            "id": f"q{index}",
            "title": f"题目 {index}",
            "prompt": candidate_prompt,
            "focus": fallback_focus,
            "follow_up_hint": "继续深挖候选人的个人贡献和判断依据。",
        }
    return None


def build_questions_with_llm(
    *,
    target_role: str,
    job_title: str,
    resume_text: str,
    highlights: list[str],
    work_experience: list[dict[str, str]],
    project_experience: list[dict[str, str]],
    technical_skills: list[str],
    planning_rag_context: str,
    planning_rag_focus_points: list[str],
    language: str,
    difficulty_level: str,
    model_provider: str,
    model_name: str,
    trace_id: str = "",
) -> tuple[list[str], list[InterviewQuestion]]:
    client = create_llm_client(model_provider, model_name)
    fallback_focus_points = merge_focus_points(
        planning_rag_focus_points,
        extract_focus_points(resume_text, highlights),
    ) or ["项目表达", "技术取舍", "问题排查", "业务理解"]
    if isinstance(client, MockLLMClient):
        focus_points = fallback_focus_points
        questions = adapt_question_difficulty(build_questions(target_role, focus_points), difficulty_level)
        log_payload(
            logger,
            logging.INFO,
            "Question generation fallback using local rules",
            {"focus_points": focus_points, "questions": questions},
            trace_id=trace_id,
        )
        return focus_points, questions

    prompt = f"""
你是一个教学版 AI 面试系统，请根据简历信息输出 JSON。

目标角色: {target_role or job_title or '后端开发工程师'}
技术语言: {language or 'Java'}
难度等级: {difficulty_level or '入门'}
亮点标签: {highlights}
技术技能: {technical_skills}
工作经历:
{_format_experience(work_experience)}

项目经历:
{_format_experience(project_experience)}

岗位知识库摘要:
{planning_rag_context or '暂无岗位知识库命中，请仅结合岗位名和简历生成题目。'}

简历原文:
{resume_text}

请返回 JSON，格式如下：
{{
  "focus_points": ["最多4个考察焦点"],
  "questions": [
    {{
      "id": "q1",
      "title": "题目标题",
      "prompt": "题目内容",
      "focus": "聚焦点",
      "follow_up_hint": "追问方向"
    }}
  ]
}}

要求：
1. 只返回 JSON。
2. 问题数量固定 4 个。
3. 问题风格偏项目深挖、技术取舍、问题排查、业务理解。
4. 结合技术语言和难度等级调整语气。
4. 不要泄露面试评分细则。
"""
    try:
        payload = client.generate_json(
            prompt,
            "你是结构化输出助手，只能返回 JSON，不要输出解释、示例或 Markdown。",
            operation_name="interview_question_generation",
            trace_id=trace_id,
        )
    except Exception:
        logger.exception(
            "[trace_id=%s] Question generation LLM JSON parse failed, fallback using local rules",
            trace_id or "-",
        )
        focus_points = fallback_focus_points
        questions = adapt_question_difficulty(build_questions(target_role, focus_points), difficulty_level)
        return focus_points, questions
    if not isinstance(payload, dict) or _looks_like_prompt_template(payload):
        logger.warning("Question generation returned invalid or template payload: %s", type(payload).__name__)
        focus_points = fallback_focus_points
        questions = adapt_question_difficulty(build_questions(target_role, focus_points), difficulty_level)
        log_payload(
            logger,
            logging.WARNING,
            "Question generation payload invalid, fallback using local rules",
            payload,
            trace_id=trace_id,
        )
        return focus_points, questions
    focus_points = _to_clean_string_list(payload.get("focus_points", []), limit=4)
    questions_raw = payload.get("questions", [])
    if not isinstance(questions_raw, list):
        logger.warning("Question generation returned invalid questions field: %s", type(questions_raw).__name__)
        questions_raw = []
    questions: list[InterviewQuestion] = []
    for index, item in enumerate(questions_raw[:4], start=1):
        normalized = _normalize_question_item(item, index=index, focus_points=focus_points)
        if normalized:
            questions.append(normalized)
    if len(questions) != 4:
        logger.warning("Question generation returned %s usable questions, fallback to deterministic questions", len(questions))
        effective_focus_points = focus_points or fallback_focus_points
        fallback_questions = adapt_question_difficulty(build_questions(target_role, effective_focus_points), difficulty_level)
        log_payload(
            logger,
            logging.WARNING,
            "Question generation usable question count invalid, fallback questions",
            {"focus_points": effective_focus_points, "questions": fallback_questions},
            trace_id=trace_id,
        )
        return effective_focus_points, fallback_questions
    log_payload(
        logger,
        logging.INFO,
        "Question generation result",
        {"focus_points": focus_points or fallback_focus_points, "questions": questions},
        trace_id=trace_id,
    )
    return focus_points or fallback_focus_points, questions


def build_follow_up(question: InterviewQuestion, answer: str) -> str:
    cleaned = answer.strip()
    focus = question.get("focus", "这个方向")
    if len(cleaned) < 40:
        return f"我听到一些关键信息了，但还不够具体。请围绕 {focus} 再补三点：你亲自做了什么、怎么验证结果、如果重来会改哪里。"
    if any(token in cleaned.lower() for token in ["ms", "qps", "%", "延迟", "成功率", "cost", "指标"]):
        return "这部分已经比较接近真实面试了。再展开一下：这些指标是怎么定义和观察的？如果结果不达标，你会先改哪里？"
    if any(token in cleaned for token in ["团队", "协作", "产品", "测试", "上线"]):
        return "不错，我想继续看你的协作与落地能力。请补充一次跨角色推进的细节：分歧是什么、你怎么推动、最后如何对结果负责？"
    return f"你的回答方向是对的。现在请把重点收敛到 {focus}，具体讲讲你做判断时参考了哪些约束，为什么没有选别的方案。"


def build_transition_to_next_question(current_question: InterviewQuestion, next_question: InterviewQuestion, answer: str) -> str:
    cleaned = answer.strip()
    current_focus = current_question.get("focus", "这个点")
    next_focus = next_question.get("focus", "下一个方向")
    if len(cleaned) < 40:
        return f"我先记下你刚才的补充，我们后面也可以继续回到 {current_focus} 深挖。接下来我想切到 {next_focus}。"
    if any(token in cleaned.lower() for token in ["ms", "qps", "%", "延迟", "成功率", "cost", "指标"]):
        return f"你刚才把结果和指标讲得比较清楚，这一点不错。接下来我想从 {next_focus} 的角度继续往下看。"
    if any(token in cleaned for token in ["团队", "协作", "产品", "测试", "上线"]):
        return f"我收到你在协作推进上的补充了，信息比较完整。下面我们切到 {next_focus}，看看你在另一个维度上的判断。"
    return f"好的，这部分我大致了解了，你刚才在 {current_focus} 上已经给出了不少信息。接下来我们换个角度，聊聊 {next_focus}。"


def build_closing_message() -> str:
    return "好的，教学版模拟面试先到这里。我已经拿到足够信息，接下来给你一份结构化总结。"


def draft_plan(state: PlanState) -> PlanState:
    provider = state.get("model_provider", "")
    model_name = state.get("model_name", "")
    trace_id = state.get("trace_id", "")
    focus_points, questions = build_questions_with_llm(
        target_role=state.get("target_role", ""),
        job_title=state.get("job_title", ""),
        language=state.get("language", ""),
        difficulty_level=state.get("difficulty_level", ""),
        resume_text=state.get("resume_text", ""),
        highlights=state.get("highlights", []),
        work_experience=state.get("work_experience", []),
        project_experience=state.get("project_experience", []),
        technical_skills=state.get("technical_skills", []),
        planning_rag_context=state.get("planning_rag_context", ""),
        planning_rag_focus_points=state.get("planning_rag_focus_points", []),
        model_provider=provider,
        model_name=model_name,
        trace_id=trace_id,
    )
    title = f"{state.get('target_role') or state.get('job_title') or 'CV'} 模拟面试"
    return {"focus_points": focus_points, "questions": questions, "session_title": title}


def pick_opening_question(state: PlanState) -> PlanState:
    current_question = state["questions"][0]
    return {"current_question": current_question, "initial_message": current_question["prompt"]}


def record_answer(state: InterviewState) -> InterviewState:
    threads = deepcopy(state.get("question_threads", []))
    current_thread = threads[state.get("current_index", 0)]
    current_thread["messages"].append({"role": "user", "kind": "answer", "content": state.get("answer", "").strip()})
    return {"question_threads": threads}


def compose_response(state: InterviewState) -> InterviewState:
    threads = deepcopy(state["question_threads"])
    questions = state["questions"]
    current_index = state.get("current_index", 0)
    current_thread = threads[current_index]
    current_question = questions[current_index]
    trace_id = state.get("trace_id", "")

    if not current_thread.get("follow_up_done", False):
        assistant_message = build_follow_up_with_llm(
            target_role=state.get("target_role", ""),
            language=state.get("language", ""),
            difficulty_level=state.get("difficulty_level", ""),
            question=current_question,
            answer=state.get("answer", ""),
            model_provider=state.get("model_provider", ""),
            model_name=state.get("model_name", ""),
            trace_id=trace_id,
        )
        current_thread["follow_up_done"] = True
        current_thread["messages"].append({"role": "assistant", "kind": "follow_up", "content": assistant_message})
        log_payload(
            logger,
            logging.INFO,
            f"Interview compose response result: current_index={current_index} action=follow_up",
            {"assistant_kind": "follow_up", "assistant_message": assistant_message},
            trace_id=trace_id,
        )
        return {
            "question_threads": threads,
            "assistant_message": assistant_message,
            "assistant_kind": "follow_up",
            "status": "active",
        }

    next_index = current_index + 1
    if next_index < len(questions):
        next_question = questions[next_index]
        transition_message = build_transition_to_next_question_with_llm(
            target_role=state.get("target_role", ""),
            language=state.get("language", ""),
            difficulty_level=state.get("difficulty_level", ""),
            current_question=current_question,
            next_question=next_question,
            answer=state.get("answer", ""),
            model_provider=state.get("model_provider", ""),
            model_name=state.get("model_name", ""),
            trace_id=trace_id,
        )
        next_question_message = f"{transition_message}\n\n{next_question['prompt']}"
        threads.append(
            {
                "question_id": next_question["id"],
                "title": next_question["title"],
                "focus": next_question["focus"],
                "follow_up_done": False,
                "messages": [{"role": "assistant", "kind": "question", "content": next_question_message}],
            }
        )
        log_payload(
            logger,
            logging.INFO,
            f"Interview compose response result: current_index={current_index} action=next_question",
            {
                "assistant_kind": "question",
                "transition_message": transition_message,
                "next_question": next_question,
                "assistant_message": next_question_message,
            },
            trace_id=trace_id,
        )
        return {
            "question_threads": threads,
            "current_index": next_index,
            "assistant_message": next_question_message,
            "assistant_kind": "question",
            "status": "active",
        }

    assistant_message = build_closing_message()
    current_thread["messages"].append({"role": "assistant", "kind": "closing", "content": assistant_message})
    log_payload(
        logger,
        logging.INFO,
        f"Interview compose response result: current_index={current_index} action=closing",
        {"assistant_kind": "closing", "assistant_message": assistant_message},
        trace_id=trace_id,
    )
    return {
        "question_threads": threads,
        "assistant_message": assistant_message,
        "assistant_kind": "closing",
        "status": "completed",
    }


def build_follow_up_with_llm(
    *,
    target_role: str,
    language: str,
    difficulty_level: str,
    question: InterviewQuestion,
    answer: str,
    model_provider: str,
    model_name: str,
    trace_id: str = "",
) -> str:
    client = create_llm_client(model_provider, model_name)
    if isinstance(client, MockLLMClient):
        return build_follow_up(question, answer)
    prompt = f"""
你是一个教学版面试官，请基于候选人的上一轮回答，生成一句自然的追问。

目标角色: {target_role or '后端开发工程师'}
技术语言: {language or 'Java'}
难度等级: {difficulty_level or '入门'}
当前题目: {question['prompt']}
考察重点: {question['focus']}
上一轮回答: {answer}
追问方向提示: {question['follow_up_hint']}

请返回 JSON，格式如下：
{{
  "message": "一句可直接说给候选人听的追问"
}}

要求：
1. 只返回 JSON。
2. message 为 40-90 字自然中文，不要分点。
3. 聚焦个人贡献、证据、判断依据，不要输出评分结论。
"""
    text = _spoken_message_from_llm(
        client,
        prompt=prompt,
        operation_name="interview_follow_up",
        trace_id=trace_id,
        fallback=build_follow_up(question, answer),
    )
    if not text:
        raise RuntimeError("大模型返回了空追问")
    log_payload(logger, logging.INFO, "Follow-up generation result", {"message": text}, trace_id=trace_id)
    return text


def build_transition_to_next_question_with_llm(
    *,
    target_role: str,
    language: str,
    difficulty_level: str,
    current_question: InterviewQuestion,
    next_question: InterviewQuestion,
    answer: str,
    model_provider: str,
    model_name: str,
    trace_id: str = "",
) -> str:
    client = create_llm_client(model_provider, model_name)
    if isinstance(client, MockLLMClient):
        return build_transition_to_next_question(current_question, next_question, answer)
    prompt = f"""
你是一个教学版面试官，请基于候选人刚刚的回答，生成一句自然的过渡话术，然后切到下一题。

目标角色: {target_role or '后端开发工程师'}
技术语言: {language or 'Java'}
难度等级: {difficulty_level or '入门'}
当前题目: {current_question['prompt']}
当前题目考察重点: {current_question['focus']}
候选人最新回答: {answer}
下一题标题: {next_question['title']}
下一题考察重点: {next_question['focus']}

请返回 JSON，格式如下：
{{
  "message": "一句可直接说给候选人听的过渡话术"
}}

要求：
1. 只返回 JSON。
2. message 为 28-60 字自然中文，不要分点。
3. 先简短接住候选人的回答，再自然转到下一题方向。
4. 不要直接复述下一题完整题干。
"""
    text = _spoken_message_from_llm(
        client,
        prompt=prompt,
        operation_name="interview_transition",
        trace_id=trace_id,
        fallback=build_transition_to_next_question(current_question, next_question, answer),
    )
    if not text:
        raise RuntimeError("大模型返回了空承接话术")
    log_payload(logger, logging.INFO, "Transition generation result", {"message": text}, trace_id=trace_id)
    return text


def evaluate(state: EvaluationState) -> EvaluationState:
    threads = state.get("question_threads", [])
    answered_questions = 0
    total_chars = 0
    focus_hits = set()

    for thread in threads:
        answers = [item["content"] for item in thread.get("messages", []) if item.get("role") == "user"]
        if answers:
            answered_questions += 1
            total_chars += sum(len(answer.strip()) for answer in answers)
            if len(" ".join(answers)) >= 80:
                focus_hits.add(thread.get("focus", "表达完整度"))

    base_score = 55 + answered_questions * 8 + min(total_chars // 80, 15)
    overall_score = max(40, min(95, int(base_score)))
    rating = "稳健" if overall_score >= 80 else "良好" if overall_score >= 70 else "待加强"

    strengths: list[str] = []
    if answered_questions >= 3:
        strengths.append("能够覆盖多道问题，表达意愿和配合度较好")
    if total_chars >= 320:
        strengths.append("回答相对展开，能补充背景、动作和结果")
    if focus_hits:
        strengths.append(f"在 {', '.join(sorted(focus_hits)[:2])} 上有一定展开")
    if not strengths:
        strengths.append("能完成基础问答，适合作为后续练习起点")

    improvements = [
        "尽量把回答收敛成背景、动作、结果三个层次，避免泛泛而谈",
        "多给出证据，例如指标、日志、复盘动作，而不只说结论",
    ]
    if total_chars < 180:
        improvements.append("当前回答偏短，建议至少准备 1-2 个可深挖的项目故事")
    if answered_questions < len(threads):
        improvements.append("部分问题没有完整展开，后续可以练习如何承接追问")

    summary = (
        f"这是一份脱敏教学版面试总结。你一共完成了 {answered_questions} 道题的回答，"
        f"当前整体表现为 {rating}，更适合继续打磨项目表达、技术取舍和复盘细节。"
    )
    result = {
        "overall_score": overall_score,
        "answered_questions": answered_questions,
        "rating": rating,
        "summary": summary,
        "strengths": strengths,
        "improvement_suggestions": improvements,
    }
    llm_result = evaluate_with_llm(
        target_role=state.get("target_role", ""),
        question_threads=threads,
        model_provider=state.get("model_provider", ""),
        model_name=state.get("model_name", ""),
        fallback=result,
        trace_id=state.get("trace_id", ""),
    )
    return {"result": llm_result}


def evaluate_with_llm(
    *,
    target_role: str,
    question_threads: list[QuestionThread],
    model_provider: str,
    model_name: str,
    fallback: dict[str, Any],
    trace_id: str = "",
) -> dict[str, Any]:
    client = create_llm_client(model_provider, model_name)
    if isinstance(client, MockLLMClient):
        log_payload(logger, logging.INFO, "Evaluation fallback result", fallback, trace_id=trace_id)
        return fallback
    prompt = f"""
你是一个教学版面试总结助手，请基于下面的问答记录，输出 JSON。

目标角色: {target_role or '后端开发工程师'}
面试记录:
{_format_threads(question_threads)}

请返回 JSON:
{{
  "overall_score": 0-100的整数,
  "answered_questions": 回答题数,
  "rating": "稳健/良好/待加强",
  "summary": "1段总结",
  "strengths": ["优势1", "优势2"],
  "improvement_suggestions": ["建议1", "建议2"]
}}

要求：
1. 只返回 JSON。
2. 结论保持教学版风格，不要输出录用建议。
"""
    payload = client.generate_json(
        prompt,
        "你是结构化输出助手，只返回 JSON。",
        operation_name="interview_evaluation",
        trace_id=trace_id,
    )
    result = {
        "overall_score": int(payload["overall_score"]),
        "answered_questions": int(payload["answered_questions"]),
        "rating": str(payload["rating"]),
        "summary": str(payload["summary"]),
        "strengths": [str(item) for item in payload["strengths"]][:3],
        "improvement_suggestions": [str(item) for item in payload["improvement_suggestions"]][:3],
    }
    log_payload(logger, logging.INFO, "Evaluation result", result, trace_id=trace_id)
    return result


plan_builder = StateGraph(PlanState)
plan_builder.add_node("draft_plan", draft_plan)
plan_builder.add_node("pick_opening_question", pick_opening_question)
plan_builder.add_edge(START, "draft_plan")
plan_builder.add_edge("draft_plan", "pick_opening_question")
plan_builder.add_edge("pick_opening_question", END)
plan_graph = plan_builder.compile()


interview_builder = StateGraph(InterviewState)
interview_builder.add_node("record_answer", record_answer)
interview_builder.add_node("compose_response", compose_response)
interview_builder.add_edge(START, "record_answer")
interview_builder.add_edge("record_answer", "compose_response")
interview_builder.add_edge("compose_response", END)
interview_graph = interview_builder.compile()


evaluation_builder = StateGraph(EvaluationState)
evaluation_builder.add_node("evaluate", evaluate)
evaluation_builder.add_edge(START, "evaluate")
evaluation_builder.add_edge("evaluate", END)
evaluation_graph = evaluation_builder.compile()


class CvInterviewWorkflow:
    def bootstrap(self, payload: dict[str, Any]) -> dict[str, Any]:
        trace_id = payload.get("trace_id", "")
        result = plan_graph.invoke(
            {
                "trace_id": trace_id,
                "job_title": payload.get("job_title", ""),
                "target_role": payload.get("target_role", ""),
                "language": payload.get("language", ""),
                "difficulty_level": payload.get("difficulty_level", ""),
                "resume_text": payload.get("resume_text", ""),
                "highlights": payload.get("highlights", []),
                "work_experience": payload.get("work_experience", []),
                "project_experience": payload.get("project_experience", []),
                "technical_skills": payload.get("technical_skills", []),
                "planning_rag_context": payload.get("planning_rag_context", ""),
                "planning_rag_focus_points": payload.get("planning_rag_focus_points", []),
                "planning_rag_sources": payload.get("planning_rag_sources", []),
                "model_provider": payload.get("model_provider", ""),
                "model_name": payload.get("model_name", ""),
            }
        )
        opening = result["current_question"]
        workflow_state = {
            "trace_id": trace_id,
            "questions": result["questions"],
            "current_index": 0,
            "status": "active",
            "target_role": payload.get("target_role", ""),
            "language": payload.get("language", ""),
            "difficulty_level": payload.get("difficulty_level", ""),
            "model_provider": payload.get("model_provider", ""),
            "model_name": payload.get("model_name", ""),
            "planning_rag_context": payload.get("planning_rag_context", ""),
            "planning_rag_focus_points": payload.get("planning_rag_focus_points", []),
            "planning_rag_sources": payload.get("planning_rag_sources", []),
            "question_threads": [
                {
                    "question_id": opening["id"],
                    "title": opening["title"],
                    "focus": opening["focus"],
                    "follow_up_done": False,
                    "messages": [{"role": "assistant", "kind": "question", "content": result["initial_message"]}],
                }
            ],
        }
        log_payload(
            logger,
            logging.INFO,
            "Interview bootstrap result",
            {"title": result["session_title"], "opening_message": result["initial_message"], "workflow_state": workflow_state},
            trace_id=trace_id,
        )
        return {
            "title": result["session_title"],
            "opening_message": result["initial_message"],
            "workflow_state": workflow_state,
        }

    def reply(self, workflow_state: dict[str, Any], answer: str) -> dict[str, Any]:
        result = interview_graph.invoke({**deepcopy(workflow_state), "answer": answer})
        updated_state = deepcopy(workflow_state)
        updated_state.update(
            {
                "question_threads": result["question_threads"],
                "current_index": result.get("current_index", workflow_state.get("current_index", 0)),
                "status": result["status"],
            }
        )
        trace_id = updated_state.get("trace_id", "")
        payload = {
            "workflow_state": updated_state,
            "assistant_message": result["assistant_message"],
            "assistant_kind": result["assistant_kind"],
            "status": result["status"],
        }
        if result["status"] == "completed":
            payload["evaluation"] = self.evaluate(updated_state)
        log_payload(
            logger,
            logging.INFO,
            "Interview reply workflow result",
            payload,
            trace_id=trace_id,
        )
        return payload

    def evaluate(self, workflow_state: dict[str, Any], target_role: str = "") -> dict[str, Any]:
        result = evaluation_graph.invoke(
            {
                "trace_id": workflow_state.get("trace_id", ""),
                "target_role": target_role or workflow_state.get("target_role", ""),
                "question_threads": workflow_state.get("question_threads", []),
                "model_provider": workflow_state.get("model_provider", ""),
                "model_name": workflow_state.get("model_name", ""),
            }
        )
        return result["result"]

    def finish(self, workflow_state: dict[str, Any]) -> dict[str, Any]:
        updated_state = deepcopy(workflow_state)
        updated_state["status"] = "completed"
        trace_id = updated_state.get("trace_id", "")
        payload = {
            "workflow_state": updated_state,
            "assistant_message": build_closing_message(),
            "assistant_kind": "closing",
            "status": "completed",
            "evaluation": self.evaluate(updated_state),
        }
        log_payload(logger, logging.INFO, "Interview finish workflow result", payload, trace_id=trace_id)
        return payload
