# 不可变契约：plan_json 如何串联三个 Agent

目录路径：实战项目 / AI面试智能体 / V2 版本优化 / 四大优化点 / Agent 协同设计：分工、人机协作 / 不可变契约：plan_json 如何串联三个 Agent

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/Tq52wxNfji6iOmkpdLmcUZkMnVb)

模块分离之后，新的问题出现了：三个模块各自独立，它们之间怎么传递信息？

先看 V1 旧方案，它是靠共用状态、直接调用函数传数据。简单来说，规划模块产出的题目，面试环节能偷偷修改，完全没有任何限制拦截。

举段代码就能直观体现这个隐患：

````
# V1：Interview 阶段可以直接修改 Planning 的产出
def adapt_question_difficulty(
    questions: list[InterviewQuestion], difficulty_level: str
) -> list[InterviewQuestion]:
    adjusted: list[InterviewQuestion] = []
    for item in questions:
        new_item = dict(item)
        new_item["difficulty_level"] = difficulty_level  # 修改了 Planning 生成的字段
        adjusted.append(new_item)
    return adjusted
````

这就是共用可变数据最典型的坑：任意流程都能中途修改同一份数据，生成这份数据的模块，根本没法保护自己的输出内容。

#### 成熟做法的参照

在多个系统之间传递数据，业界有几种主流方式：

1. 不可变消息：数据生成出来就固定死，下游只能读取，无权改动。像事件驱动、消息队列这类系统基本都是这么设计的。

2. 带版本的接口契约：上下游提前约定好带版本号的数据规范，只要字段有改动就升级版本，杜绝偷偷修改数据的情况。

3. 只读视图：数据库只给下游查询权限，代码里也用不可变数据结构，从根源不让下游写入修改。

V2 采用了不可变消息方案，同时搭配带版本的数据规范：规划智能体生成好 plan_json，等用户确认后就存入数据库，状态标记为已确认。

界面示例：

![页面图片](../assets/351-468659d2fb724f65.png)

后面面试、评分模块只能凭这份计划的ID读取内容，完全没有修改权限。

面试 Agent 代码判断示例：

（如果会话状态不是「已确认计划」，直接抛出 409 错误，提示用户必须先锁定面试计划）

````
# offer-agent/backend/app/services/interview_agent_service.py
if record["status"] != InterviewPlanSessionStatus.PLAN_CONFIRMED.value:
    raise_app_error(409, ErrorCode.SESSION_NOT_ACTIVE, "请先确认并锁定面试计划")

confirmed_plan_id = record.get("confirmed_plan_id")
plan_record = self.store.get_plan_by_id(confirmed_plan_id)
plan_json = plan_record["plan_json"]
````

只有校验通过，才会拿确认后的计划 ID 去数据库拉取完整计划数据。

#### plan_json 的结构

plan_json 是一个 JSON 对象，描述一场面试的完整蓝图。核心是一个主题列表，每个主题包含：

````
{
  "topics": [
    {
      "id": "topic-1",
      "name": "项目所有权",
      "dimension": "项目经历真实性验证",
      "objective": "验证候选人的真实职责和个人贡献",
      "focus_points": ["核心项目", "个人职责边界"],
      "required": true,
      "estimated_minutes": 8,
      "max_rounds": 3,
      "opening_question": "请介绍一个你觉得最能代表自己的项目...",
      "expected_signals": ["职责边界清晰", "个人贡献可量化"],
      "probe_strategies": ["追问具体决策与结果"],
      "evaluation_criteria": "职责描述是否具体、可验证"
    }
  ],
  "duration_minutes": 45,
  "max_answer_rounds": 12,
  "closing_buffer_minutes": 5
}
````

这些字段不是随意定义的，而是按照下游消费方的需求设计的。面试 Agent 和 评估 Agent 各自消费不同的字段子集：

- 面试 Agent 消费的是「怎么考」：按 topics 顺序推进，用 objective、focus_points、expected_signals、probe_strategies 驱动每轮对话，以此保证整场对话不偏离计划里的考察主题和信号

- 评估 Agent 消费的是「怎么评」：严格遍历 plan 里的每个 topic，用 expected_signals 和 focus_points 作期望信号全集，对照面试中抽取的结构化证据推导三态和分数；

这样分工的结果是：面试负责按计划把信号考出来，评估负责按同一套信号验出来——问什么和评什么，始终对齐同一份计划。

具体消费情况如下：

| 字段 | 消费方 | 用途 |
| --- | --- | --- |
| opening_question | 面试 Agent | 每个主题的首问来源，允许口语化改写 |
| expected_signals | 面试 Agent + 评估 Agent | Decide 的追问依据；评估的信号覆盖判定 |
| probe_strategies | 面试 Agent | Decide Prompt 里的追问 hint，非固定脚本 |
| evaluation_criteria | 评估 Agent | 评分参考标准，不进入面试话术 |
| dimension | 两者共用 | Interview 的上下文标注；Evaluation 的维度分类 |
| max_rounds / duration_minutes | 面试 Agent | boundaries.py 读取，作为硬边界强制执行 |

最终三个 agent 的整体串联流程如下：

> 图片尚未保存：[在原页面查看](https://acn2lw4rwc26.feishu.cn/wiki/Tq52wxNfji6iOmkpdLmcUZkMnVb)（图片标识：Gk4WbANjNoy9bUxFuSEcl7PLnxb）