# LangGraph：基于状态机实现面试对话

目录路径：实战项目 / AI面试智能体 / V1 版本开发 / 核心难点 / LangGraph：基于状态机实现面试对话

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/UqITwxUF5iZTNqk9TkDcW2LUnAf)

面试对话和普通闲聊有本质区别：它全程依赖上下文状态。系统需要记住当前进行到第几题、题目是否发起过追问、完整聊天记录等信息，才能推进后续流程。但我们常用的 HTTP 协议本身是无状态的，单次请求结束后，服务端不会保留任何会话数据。

这篇文章就讲这个矛盾怎么解决，以及 LangGraph 在里面扮演的角色。

本文核心要点：

1. 针对面试场景设计独立对话线程 QuestionThread，替代全局消息列表

2. 基于 plan_graph 前置完成面试题目生成与初始化

3. 拆解 interview_graph 核心节点，实现追问、切题、结束面试的状态流转

4. 通过状态持久化，解决 HTTP 无状态与对话有状态的冲突

5. 结合 AI 完成状态结构迭代与规范优化

![页面图片](../assets/329-5414b79f0fed1186.png)

#### 面试为什么不用全局消息列表？

普通聊天只需要一个全局 messages 数组就够了。 但面试不行，因为：

- 要按题目管理对话

- 要知道是否已追问

- 要按题评分、复盘

- 要存题目焦点、追问状态等元数据

全局消息列表做不到这些，所以我们必须给每道题创建独立的对话线程 QuestionThread。

1. 线程结构定义

````
class QuestionThread(TypedDict):
    question_id: str      # 题目唯一ID
    title: str            # 题目标题，用于前端展示
    focus: str            # 题目考察重点，作为追问LLM的上下文
    follow_up_done: bool  # 标记当前题目是否已完成追问（核心控制字段）
    messages: list[ThreadMessage]  # 本题完整对话记录
````

其中 follow_up_done 是流程控制的核心：系统会根据这个字段，判断下一步是继续追问、切换下一题，还是结束面试。focus 则用于约束追问方向，让问题紧扣题目考察点。

2. 结构示例与消息类型

一条完整的单题对话线程示例如下：

````
{
  "question_id": "q2",
  "title": "技术决策",
  "focus": "技术取舍",
  "follow_up_done": false,
  "messages": [
    {
      "role": "assistant",
      "kind": "question",
      "content": "如果把这段经历放到后端工程师的场景里，你做过或会怎么做一次关键技术决策？"
    },
    {
      "role": "user",
      "kind": "answer",
      "content": "我们当时选了 Redis 做缓存，主要是考虑读多写少的场景。"
    }
  ]
}
````

消息通过 kind 字段细分类型：question 为面试官原题、answer 为用户回答、follow_up 为追问问题、closing 为结束语。前端可依据该字段区分样式，单纯依靠 role 无法满足精细化渲染需求。

这套结构是结合需求逐步通过 AI 优化而来：最初仅定义了 messages 和 follow_up_done 基础字段；结合追问场景，补充了 focus 考察点字段；为适配前端渲染，又新增 kind 区分消息类型，最终形成完整可用的设计。

#### 前置工作流：plan_graph 生成面试题目

面试要先有题，才能开始对话。 所以最先运行的是出题工作流 plan_graph。

这套工作流分为两步：

1. draft_plan：结合简历信息 + RAG 检索的参考内容，批量生成面试题目；RAG 结果会提前写入工作流状态并持久化，后续答题环节直接复用，无需重复检索；

2. pick_opening_question：从题目列表中选出第一道题，生成开场内容。

流程初始化完成后，系统会自动为第一道题创建 QuestionThread。这里采用双层状态设计：数据库会话表状态标记为 preparing（面向前端，标识面试待开始），LangGraph 内部状态标记为 active（面向工作流，标识可执行对话逻辑），两层状态各司其职。

#### 面试工作流：interview_graph 流程拆解

题目准备好，就进入真正的面试对话流程。

整个 interview_graph 由两个节点串成一条直线：

````
record_answer → compose_response
````

1. 节点一：record_answer 负责记录用户回答

该节点的作用很纯粹：读取当前工作流状态，把用户最新回答追加到对应题目的对话线程QuestionThread中。

````
def record_answer(state: InterviewState) -> InterviewState:
    threads = deepcopy(state.get("question_threads", []))
    current_thread = threads[state.get("current_index", 0)]
    current_thread["messages"].append({
        "role": "user",
        "kind": "answer",
        "content": state.get("answer", "").strip(),
    })
    return {"question_threads": threads}
````

开发时需要注意：修改状态前必须对线程数据做深拷贝。LangGraph 遵循增量更新原则，直接修改原始状态会引发数据污染问题，深拷贝能保证原始数据不受影响。执行完成后，仅返回更新后的线程数据。

2. 节点二：compose_response 决策下一步动作

这是整个面试流程的核心决策节点。它会读取最新状态，决定做三件事中的哪一件：追问、切题、还是结束。三个分支互斥，执行完一个就返回。

````
def compose_response(state: InterviewState) -> InterviewState:
    threads = deepcopy(state["question_threads"])
    questions = state["questions"]
    current_index = state.get("current_index", 0)
    current_thread = threads[current_index]
    current_question = questions[current_index]

    # 分支一：当前题还没追问过，执行追问
    if not current_thread.get("follow_up_done", False):
        assistant_message = build_follow_up_with_llm(
            question=current_question,
            answer=state.get("answer", ""),
            ...
        )
        current_thread["follow_up_done"] = True
        current_thread["messages"].append({
            "role": "assistant",
            "kind": "follow_up",
            "content": assistant_message
        })
        return {
            "question_threads": threads,
            "assistant_message": assistant_message,
            "assistant_kind": "follow_up",
            "status": "active",
        }

    # 分支二：当前题已追问，还有下一题，切换题目
    next_index = current_index + 1
    if next_index < len(questions):
        next_question = questions[next_index]
        transition_message = build_transition_to_next_question_with_llm(
            current_question=current_question,
            next_question=next_question,
            answer=state.get("answer", ""),
            ...
        )
        next_question_message = f"{transition_message}\n\n{next_question['prompt']}"
        threads.append({
            "question_id": next_question["id"],
            "title": next_question["title"],
            "focus": next_question["focus"],
            "follow_up_done": False,
            "messages": [{"role": "assistant", "kind": "question", "content": next_question_message}],
        })
        return {
            "question_threads": threads,
            "current_index": next_index,
            "assistant_message": next_question_message,
            "assistant_kind": "question",
            "status": "active",
        }

    # 分支三：所有题都问完了，结束面试
    assistant_message = build_closing_message()
    current_thread["messages"].append({
        "role": "assistant", "kind": "closing", "content": assistant_message
    })
    return {
        "question_threads": threads,
        "assistant_message": assistant_message,
        "assistant_kind": "closing",
        "status": "completed",
    }
````

切换题目时，新线程会直接追加到线程列表末尾，答题索引同步递增。这里要区分一个细节：线程列表长度代表已创建的题目数量，不等于用户已回答的题目数量。

#### 解决 HTTP 无状态问题

前面所有设计：QuestionThread、plan_graph、interview_graph，都依赖 LangGraph 内存 state 运行。但 HTTP 请求一结束，内存里的 state 就消失。 下一次请求进来，graph 完全不知道之前发生了什么。

针对这个矛盾，我们采用状态持久化方案，把 LangGraph 的内存状态落地到数据库中，下次请求进来，先从数据库读回来，再继续执行。这就把无状态 HTTP 变成了 有状态工作流。

项目里同时维护两份对话相关数据，职责不同：

- workflow_state_json：存 questions、question_threads、current_index 等，供 LangGraph 推理和评分。

- messages 表：按条持久化用户回答和 AI 回复，供前端渲染聊天界面。

答题接口 interview_service.reply_to_interview 串联起「读取持久化状态 → 执行工作流 → 回写状态」全流程，完美适配 HTTP 请求模式：

1. 从数据库读取会话信息，校验会话状态，仅运行中的会话允许提交回答；

2. 先将用户回答存入消息表，用于前端渲染；

3. 加载数据库中持久化的 workflow_state，传入 interview_graph 执行对话逻辑；

4. 将 Graph 生成的 AI 回复存入消息表；

5. 把 Graph 输出的最新状态序列化，更新到数据库中。

代码示例：

````
def reply_to_interview(self, user_id: int, session_id: str, answer: str) -> dict[str, Any]:
    session = self.store.get_session(user_id, session_id)
    # 仅 active 状态的会话可答题
    if session["status"] != InterviewSessionStatus.ACTIVE.value:
        raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先正式开始面试")

    user_message = self.store.create_message(
        session_id=session_id, role="user", kind="answer", content=answer,
    )
    result = self.workflow.reply(session["workflow_state"], answer)

    assistant_message = self.store.create_message(
        session_id=session_id,
        role="assistant",
        kind=result["assistant_kind"],
        content=result["assistant_message"],
    )
    self.store.update_session(
        session_id,
        status=result["status"],
        workflow_state=result["workflow_state"],
        evaluation=result.get("evaluation"),
    )
    return {"session": ..., "user_message": user_message, "assistant_message": assistant_message}
````

当所有题目回答完毕、会话状态变为 completed 时，系统会自动调用评分工作流 evaluation_graph 生成面试评分，并将评分数据一并落库。如果用户主动点击「结束面试」，也会触发相同的评分逻辑，二者只是触发路径不同。

落地注意事项

1. 状态增量合并：LangGraph 节点只会返回本轮执行中变更的字段，不会返回完整状态。比如「追问」场景不会更新题号索引，合并数据时需要用旧状态字段兜底，避免数据丢失；

2. JSON 序列化约束：存入数据库的状态必须支持 JSON 序列化。因此状态中仅允许存放字符串、数字、布尔、列表、字典等基础类型，禁止存放 LLM 实例、时间对象等特殊 Python 对象。

#### 用 AI 优化状态结构

项目初期的状态结构存在两处不合理设计，影响代码整洁度与可维护性，我们借助 AI 快速迭代优化。

早期状态的两个核心问题：

1. 数据层级混乱：state 结构扁平，顶层同时混杂持久数据（对话线程、题目信息）和临时输入数据（单次用户回答），数据边界模糊。

2. 命名不统一：题号字段存在 current_question_index、question_index 等多种写法，代码可读性差。

把这些问题描述给 AI，大致的 prompt 是：

````
state 里混着持久字段和临时字段，比如 answer 每次都要从外部注入，但又不想它被持久化。
有什么干净的方式处理？另外字段命名比较乱，能帮我整理一下命名规范吗？
````

AI 据此给出两条优化建议：

- 一是单独区分临时字段，在数据存入数据库前主动清空这类字段，避免无效数据落地；

- 二是统一命名风格，简化字段名称，例如用current_index替代冗长的current_question_index，用answer统一代替user_answer。

结合项目实际场景，我们对方案做了取舍： 对于「落库前清空临时字段」的方案，最终没有完全采纳。该操作会新增额外的处理逻辑，还存在漏清理的风险。而本项目中，answer仅作为单次工作流的入参，record_answer节点会将内容同步写入对应的对话线程。即便顶层的answer字段被一并持久化也不会影响流程，因为下一轮请求会注入新数据自动覆盖旧值，无需额外做清理动作。

对于「统一命名规范」的建议，则全面落地。最终统一使用精简名称：answer、current_index、assistant_message，全项目保持一致，代码的可读性和一致性大幅提升。

其实状态结构设计没有绝对完美的标准答案，核心是结合业务场景权衡利弊，打造出够用、稳定、低维护成本的方案。在这个过程中，AI 更多是帮我们梳理问题、罗列可行方案，而结合项目现状做最终决策与取舍，依然需要开发者自主判断。