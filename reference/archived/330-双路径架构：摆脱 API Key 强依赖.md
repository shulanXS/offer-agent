# 双路径架构：摆脱 API Key 强依赖

目录路径：实战项目 / AI面试智能体 / V1 版本开发 / 核心难点 / 双路径架构：摆脱 API Key 强依赖

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/PEm0wtLMAiBgeAkXvorcFAKwn4f)

开发 AI 类项目常会遇到一类现实难题：本地调试、离线演示环境中，往往缺少 API Key。如果靠注释业务代码、零散编写调试判断逻辑，不仅代码臃肿，还容易埋下隐患。本文介绍双路径架构，一套代码同时支持「真实 LLM 调用」和「本地规则模拟」，无需改动业务代码，就能灵活切换运行模式。

![页面图片](../assets/330-0b6ee665d7a54f63.png)

#### 双路径的设计原则

这套架构为 AI 操作设计两条等价执行链路，切换逻辑简单、侵入性极低，整体遵循三条设计原则：

1. 规则逻辑等价可用：模拟路径并非简单返回空数据或固定占位内容，而是实现完整业务逻辑，输出结果与真实 LLM 在格式、业务合理性上保持一致。

2. 接口完全对齐：两条路径入参、出参、异常规则完全统一，上层调用方无法感知当前走的是远程模型还是本地规则。

3. 配置驱动切换：仅修改配置项  LLM_PROVIDER 即可切换运行模式，无需改动任何业务代码。本质是基于依赖注入思想，业务层只依赖通用客户端接口，不绑定具体实现。

项目中 LLM 对话、向量 RAG 能力均采用该思路独立配置：前者由 LLM_PROVIDER 控制，后者由 RAG_EMBEDDING_PROVIDER 控制（local / openai）。思路相同，都是"有 Key 走远程、没 Key 走本地"，只是变量名不同。

#### 统一客户端接口与 Mock 实现

整个架构以抽象客户端基类为基础，区分真实客户端与模拟客户端，统一调用标准。

1. 抽象基类 LLMClient

所有大模型客户端都继承该抽象类，定义统一调用方法：

````
class LLMClient(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> str:
        raise NotImplementedError

    def generate_json(self, prompt, system_prompt=None, *, operation_name, trace_id) -> Any:
        # 默认实现：调用 generate_text，再解析 JSON
        response_text = self.generate_text(prompt, system_prompt, ...)
        return _extract_json(response_text)
````

2. MockLLMClient 继承了这个基类

模拟客户端仅作为模式标识，不单独实现业务规则。如果被直接调用会主动抛出异常，避免静默报错隐藏问题：

````
class MockLLMClient(LLMClient):
    def __init__(self, model_name: str = "mock") -> None:
        self.provider_name = "mock"
        self.model_name = model_name

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        *,
        operation_name: str = "generic",
        trace_id: str = "",
    ) -> str:
        raise RuntimeError("mock client should not be called directly")
````

#### 工厂函数：根据配置分发客户端

create_llm_client 工厂函数负责读取全局配置，自动创建对应客户端，是模式切换的核心入口。函数不缓存实例，每次调用都会读取最新配置：

````
def create_llm_client(provider: str | None = None, model_name: str | None = None) -> LLMClient:
    selected_provider = (provider or settings.llm_provider or "mock").strip().lower()

    if selected_provider in {"mock", ""}:
        return MockLLMClient(model_name or "mock")

    if selected_provider in {"openai"}:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY 未配置")
        model = ChatOpenAI(api_key=settings.openai_api_key, ...)
        return LangChainLLMClient("openai", model_name or "gpt-4o-mini", model)

    if selected_provider in {"anthropic", "claude", "claude_code"}:
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        # 填写自定义 ANTHROPIC_BASE_URL 时，会自动加 Authorization: Bearer 头
        model = ChatAnthropic(...)
        return LangChainLLMClient("anthropic", model_name or "claude-3-5-sonnet-20241022", model)

    if selected_provider in {"volcengine", "volc", "ark", "huoshan"}:
        if not settings.volcengine_api_key:
            raise ValueError("VOLCENGINE_API_KEY 未配置")
        model = ChatOpenAI(
            api_key=settings.volcengine_api_key,
            base_url=settings.volcengine_base_url,
            model=model_name or "doubao-seed-1-6-flash-250715",
            ...
        )
        return LangChainLLMClient("volcengine", model_name or "doubao-seed-1-6-flash-250715", model)

    raise ValueError(f"不支持的 LLM_PROVIDER: {selected_provider}")
````

没有配置 LLM_PROVIDER，或者配置成 mock，就返回 MockLLMClient。其他情况返回对应的 LangChainLLMClient（支持 OpenAI、Anthropic、火山引擎）。

工厂每次被调用时都读取当前配置，不缓存，所以理论上可以在运行时切换——不过实际项目里通常只需要在启动前配置好。

#### 业务节点：落地双路径调用逻辑

所有需要调用大模型的业务节点，都遵循同一套判断逻辑：先通过工厂获取客户端，再判断客户端类型，分流至本地规则或远程 LLM；部分场景还增加异常兜底，进一步提升稳定性。

1. 面试出题场景

出题逻辑包含三层容错：Mock 模式直接走本地规则、LLM 正常调用走远程、LLM 返回格式异常自动回退到规则逻辑：

````
def build_questions_with_llm(...) -> tuple[list[str], list[InterviewQuestion]]:
    client = create_llm_client(model_provider, model_name)

    # isinstance 检查触发路径选择
    if isinstance(client, MockLLMClient):
        focus_points = extract_focus_points(resume_text, highlights)
        questions = adapt_question_difficulty(
            build_questions(target_role, focus_points),
            difficulty_level
        )
        return focus_points, questions

    # LLM 路径：构造 prompt，调用真实 LLM
    try:
        payload = client.generate_json(prompt, "你是结构化输出助手，只能返回 JSON。", ...)
    except Exception:
        # JSON 解析失败，回退到规则路径
        return fallback_focus_points, adapt_question_difficulty(
            build_questions(target_role, fallback_focus_points), difficulty_level
        )
    if not isinstance(payload, dict) or _looks_like_prompt_template(payload):
        # echo-back 或结构非法，同样回退
        return fallback_focus_points, adapt_question_difficulty(
            build_questions(target_role, fallback_focus_points), difficulty_level
        )
    # 校验通过后规范化 payload
    ...
    return focus_points, questions
````

本地规则并非虚假数据：extract_focus_points 提取简历技术要点，build_questions 生成结构化面试题，adapt_question_difficulty 调整题目难度，整套逻辑具备完整业务能力。

2. 面试追问场景

追问场景同样区分双路径，规则路径依靠关键词、文本长度匹配固定模板生成内容：

````
def build_follow_up_with_llm(*, question, answer, model_provider, model_name, ...) -> str:
    client = create_llm_client(model_provider, model_name)

    # Mock模式：本地规则生成追问
    if isinstance(client, MockLLMClient):
        return build_follow_up(question, answer)
    # LLM模式：拼接提示词调用远程模型
    prompt = f"""
你是一个面试官，请基于候选人的上一轮回答，生成一句自然的追问。
当前题目: {question['prompt']}
考察重点: {question['focus']}
上一轮回答: {answer}
...
"""
    return client.generate_text(prompt, "你是面试官，只输出追问本身。", ...).strip()
````

两者都能推进面试对话，只是灵活度不同。

#### 双路径覆盖一览

项目核心 AI 能力均已实现双路径适配，同时标注异常兜底策略：

| 操作 | 规则路径（mock） | LLM 路径 | LLM 失败回退 |
| --- | --- | --- | --- |
| 面试出题 | build_questions + 规则 | generate_json | 支持回退 |
| 题目追问 | build_follow_up | generate_text | 不回退 |
| 题目切题过渡 | build_transition_to_next_question | generate_text | 不回退 |
| 面试评分 | 规则算分 | evaluate_with_llm | mock 时用规则结果 |
| 简历解析 | _parse_with_rules | _parse_with_llm | 返回异常提示 |

#### 用 AI 写规则路径

规则路径的逻辑可以借助 AI 辅助开发，大幅提升编码效率，实操流程如下：

1. 明确输出规范：将 LLM 要求的 JSON 格式、字段约束、业务示例提供给 AI；

2. 描述业务逻辑：告知 AI 需要实现的功能，要求不调用外部服务，纯本地逻辑实现；

3. 人工二次优化：修正 AI 生成内容中口语化、泛化描述等问题，补充缺失字段。

使用时建议附带真实样例，约束字段细节（如focus需填写具体技术点，而非 “技术能力” 这类笼统描述），能有效提升规则内容质量。

#### 双路径的额外价值

双路径设计最初是为了解决"没有 API Key 也能跑"的问题，但它带来了几个意外收益。

- 调试更方便。 LLM 的输出具有随机性，同一个 prompt 每次返回的内容可能不同。调试时你想复现一个特定场景，LLM 路径很难稳定复现。规则路径的输出是确定的，给定相同输入永远返回相同结果，问题很容易重现和定位。

- 开发速度更快。 真实 LLM 调用有延迟，快的要 1-2 秒，慢的要十几秒。开发和调试前端时，如果每次交互都要等 LLM 响应，效率极低。mock 模式下接口瞬间返回，前端开发可以和后端完全解耦。

- 天然的测试隔离。 mock 模式本质上是一种测试替身（test double）。自动化测试可以直接用 mock 模式跑，不需要任何真实 API Key。