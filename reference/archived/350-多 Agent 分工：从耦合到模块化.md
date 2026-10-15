# 多 Agent 分工：从耦合到模块化

目录路径：实战项目 / AI面试智能体 / V2 版本优化 / 四大优化点 / Agent 协同设计：分工、人机协作 / 多 Agent 分工：从耦合到模块化

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/UA0lw8wrAi7oCJkr7hucTWemn3T)

V1 的面试系统在工程层面有一个值得注意的特征：规划、对话、评估三个阶段的核心代码，全部写在 backend/app/agent/workflow.py 这一个文件里。

![页面图片](../assets/350-b68a38d05a956db8.png)

V2 把三个模块彻底分开，每个阶段有自己独立的目录：

````
backend/app/agent/
├── interview_planning/      # 规划阶段
│   ├── agent.py             # LLM 调用、重试、降级
│   ├── validator.py         # 结构校验与维度检查
│   ├── templates.py         # 模板降级
│   └── prompts.py           # Prompt 组装
├── interview/               # 对话阶段
│   ├── graph.py             # LangGraph StateGraph
│   ├── decide.py            # 决策 Agent
│   ├── routing.py           # 条件边路由
│   └── nodes/               # 各节点实现
└── interview_evaluation/    # 评估阶段
    ├── agent.py
    ├── validator.py
    └── prompts.py
````

每个模块各自管理自己的状态类型、Prompt 逻辑、LLM 调用和校验规则。模块之间不共享代码，只通过明确的数据结构传递信息。

#### 分工之后的优势

分开目录不只是整理代码好看，实打实解决了一堆旧版痛点：

1. 可以单独写单元测试

V2 的测试文件完全拆分，test_interview_planning.py 只测规划全流程接口，test_planning_validator.py 专门测各种极端校验场景，和面试对话模块完全隔离。 但 V1 三个阶段的状态定义全挤在一个文件，随便跑一个测试，都会加载全部代码依赖，特别笨重。

2. 修改范围能精准控制

比如只想调整规划模块的校验规则，直接打开 interview_planning/validator.py，里面完全看不到面试、评估的业务代码。改其中一个模块，完全不会误影响另外两块。

3. 模块之间的调用边界一目了然

规划模块不能直接调用面试模块里的内部函数，跨模块传数据只能走提前约定好的统一数据契约 plan_json。 别人看代码的时候，能一眼看清模块之间靠什么数据交互，不用靠脑子硬记一堆共享变量的流转逻辑。