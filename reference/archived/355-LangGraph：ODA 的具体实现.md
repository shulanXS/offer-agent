# LangGraph：ODA 的具体实现

目录路径：实战项目 / AI面试智能体 / V2 版本优化 / 四大优化点 / Agent 决策架构：ODA、LangGraph与可靠性 / LangGraph：ODA 的具体实现

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/UElcwR9DribTO7k1BwIcOi1Fnpc)

上一篇我们讲完 ODA 三层分工，本篇解决一个核心问题：观察、决策、话术生成这些独立环节，在代码里靠什么有序串起来自动运行。

整套链路使用 LangGraph 作为流程编排引擎。它不写业务提示词、不调用大模型生成内容，只做三件调度工作：控制函数执行顺序、按场景走不同分支、统一存放全流程中间数据。

#### V1 和 V2 都用 LangGraph，差别在哪？

V1版本虽然也接入了 LangGraph，但只用了它最基础的能力：仅把固定流程连成一条直线，所有分支、判断逻辑全都写在节点内部的 if/else 代码中。

V2充分发挥 LangGraph 完整能力，搭建出完整 ODA 数据流水线，所有分支走向全部对外显式配置，不再藏在业务代码里。

![页面图片](../assets/355-37710261856df421.png)

#### 整体分工

LangGraph 整套执行链路可以理解为一条数据流水线，分为三层核心角色，定位互不重叠：

1. Node（节点）：承载业务逻辑的独立函数，比如 decide 节点调用大模型输出决策；

2. LangGraph 编排引擎：负责串联所有节点，管控执行顺序，同时支持动态分支跳转；

3. State（全局状态）：全流程共用的数据载体，数据在各个节点之间传递流转。

整条流水线固定流转逻辑： State 全局状态传入 Node 节点 → 节点读取并更新 State → 通过 LangGraph 的连线传给下一个节点；若遇到动态分支，引擎会读取 State 里的字段自动选择后续路径，循环执行直到流程结束。

![页面图片](../assets/355-34668ff928142960.png)

#### 三大核心概念

##### Node 节点：流水线独立业务单元

Node 是流水线中最小的业务执行单元，本质是纯函数。所有节点统一遵循固定签名：输入全局 State、处理业务、返回更新后的 State。

节点有两条严格设计规范：

1. 只做计算、不做 IO：仅负责数据处理与 LLM 调用，不直接写数据库、不推送前端流式消息；数据持久化、消息推送统一由外层服务接管。

2. 单一职责：一个节点只专注完成一类业务逻辑，职责高度内聚。

以边界校验节点为例，它只会根据规则生成边界判断结果，仅更新 State 中的 boundary 字段，其余数据原样透传，保证节点逻辑纯粹、无副作用：

````
# offer-agent/backend/app/agent/interview/nodes/boundaries.py
def enforce_boundaries_node(state: InterviewReplyState) -> InterviewReplyState:
    verdict = evaluate_forced_action(
        runtime_state=state["runtime_state"],
        plan_json=state["plan_json"],
        current_topic_id=state["current_topic_id"],
    )
    return {
        **state,
        "boundary": {
            "forced_action": verdict.forced_action,
            "reason": verdict.reason,
        },
    }
````

##### State 全局状态：流水线统一数据载体

所有节点之间不会互相传参，统一共用 InterviewReplyState 字典，每个节点遵守3条规则：

1. 读取 State 里全部已有信息，比如面试方案、候选人回答、上一节点输出等；

2. 运算完成只更新自己业务对应的字段；

3. 把更新后的完整 State 传给下一个节点。

全局状态完整定义存放于 state.py 文件，日常开发只需重点关注两个控制分支走向的核心字段：boundary、decision。

````
# offer-agent/backend/app/agent/interview/state.py 关键字段节选
class InterviewReplyState(TypedDict, total=False):
    # 流程输入
    plan_json: dict[str, Any]
    latest_answer: str
    runtime_state: dict[str, Any]
    # 分支控制中间状态
    boundary: dict[str, Any]
    decision: dict[str, Any]
    # 最终输出话术
    assistant_content: str
````

##### 条件边：流水线动态分支岔路口

LangGraph 提供两类节点连接方式，用来控制流程流转：

1. 普通固定边：上一节点执行完成后，会固定流转到指定下一节点，执行顺序不会变动；

2. 条件分支边：节点执行结束后，会执行轻量化路由函数。该函数仅读取全局状态，不会调用大模型，最后返回分支标识，LangGraph 依据标识切换后续流程走向。

整条流水线仅设置两处核心分支判断逻辑：

| 触发分支的前置节点 | 判断依赖的State字段 | 可选流程走向 |
| --- | --- | --- |
| enforce_boundaries 执行完成后 | boundary.forced_action | 强制结束流程、强制切换题目、正常继续执行 |
| decide 执行完成后 | decision.action | 发起追问、拦截重复提问、切换题目或结束流程 |

路由代码示例：

````
# offer-agent/backend/app/agent/interview/routing.py
def route_after_boundary(state) -> Literal["finish", "next_topic", "continue"]:
    forced = (state.get("boundary") or {}).get("forced_action")
    if forced == "finish":
        return "finish"
    if forced == "next_topic":
        return "next_topic"
    return "continue"
````

#### 完整流水线实际流转演示

> 图片尚未保存：[在原页面查看](https://acn2lw4rwc26.feishu.cn/wiki/UElcwR9DribTO7k1BwIcOi1Fnpc)（图片标识：TW1GbPo9noNRZAxRBYlc2wrwnMe）

两种场景对比能清晰看出：LangGraph 只管控流水线顺序与分支切换，业务 Prompt、LLM 交互逻辑全部封装在各个Node 节点内部。

#### graph.py：流水线组装配置文件

graph.py 不包含任何业务计算逻辑，只做节点注册、连线、分支配置，最终编译生成可运行流程图。

````
# offer-agent/backend/app/agent/interview/graph.py 
_builder = StateGraph(InterviewReplyState)

# 注册业务节点
_builder.add_node("decide", decide_node)
_builder.add_node("act_probe", act_probe_node)

# 固定连线
_builder.add_edge("merge_working_memory", "decide")

# 配置条件分支
_builder.add_conditional_edges(
    "decide",
    route_after_decide,
    {"probe": "act_probe", "advance": "finalize_advance", ...},
)

interview_reply_graph = _builder.compile()
````

迭代维护的修改边界划分十分清晰：

- 若调整证据提取、决策、话术生成等业务逻辑，只需修改对应 Node 文件；

- 若新增流程分支、调整节点执行顺序，则修改 graph.py 与 routing.py。

流程编排逻辑与业务计算代码完全解耦，这也是选用 LangGraph 最核心的优势。