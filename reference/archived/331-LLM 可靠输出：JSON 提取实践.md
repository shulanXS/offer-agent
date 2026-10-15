# LLM 可靠输出：JSON 提取实践

目录路径：实战项目 / AI面试智能体 / V1 版本开发 / 核心难点 / LLM 可靠输出：JSON 提取实践

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/FkdtwqRRDiY7GhkXgNMcsOr9n4e)

LLM 是概率模型，即使你用了完全相同的 prompt，每次输出的格式也可能不一样。这在对话场景里还好接受，用户能看懂大意就行。但在 Agent 系统里，AI 输出的 JSON 要喂给下一个节点，格式一旦不对，整条链路就断了。

本文结合项目实战，讲解一套多层防护、针对性解决典型异常的 JSON 提取方案。

#### 原有基础方案与现存短板

此前在 harnessprd 项目已经讲过成熟的 JSON 提取降级逻辑，核心分为两层：先剔除 Markdown 代码块标记，再依次通过json.loads、正则表达式兜底提取内容，部分方案还支持调用 LLM 自主修正异常输出。参考文档：
[JSON 与运行时问题实录](https://acn2lw4rwc26.feishu.cn/wiki/I7wCwxGdRiyV4sk4rbMclRc1npg?fromScene=spaceOverview)

本项目沿用前两层基础逻辑，并新增多候选打分能力，完整执行流程如下：

1. 移除文本中```json等代码块标记

2. 遍历解析出所有 JSON 候选内容，按关键字段匹配度打分，选取最优结果

3. 无合格候选时，直接整段执行json.loads解析

4. 解析失败则通过正则匹配{}片段做最后兜底

![页面图片](../assets/331-10d2306a1f5afe16.png)

在落地过程中，我们遇到了两套原有方案无法解决的新问题：

- 一是同一段文本内包含多个 JSON 对象，不知道该用哪个；

- 二是 LLM 把 prompt 模板本身当成答案返回（echo-back），语法合法但无实际业务价值。

下文针对这两类问题逐一拆解解决方案。

#### 解决多 JSON 混杂问题：多候选打分

简单正则提取 JSON 有一个前提假设：文本中仅存在单个 JSON 对象。但 LLM 常会在 JSON 前后附加自然语言说明，或是一次性输出多个独立 JSON。

举个例子，生成面试题时模型可能返回如下内容：

````
好的，这道题考察候选人对分布式锁的理解。评分参考如下：

{"max_score": 10, "dimensions": ["正确性", "完整性"]}

以下是题目内容：

{"focus_points": ["分布式锁"], "questions": [{"id": "q1", "title": "Redis锁", ...}]}
````

文本里同时存在评分、面试题两组 JSON，直接截取第一个会拿到错误数据，影响后续流程。

##### 解决思路

解决思路是把文本里所有合法的 JSON 对象都提取出来，然后根据本项目期望的关键字段做打分，选得分最高的那个，而不是"第一个能解析的"。

1. 遍历提取全部 JSON 候选

借助json.JSONDecoder.raw_decode逐段扫描文本，兼容嵌套 JSON、连续多 JSON 等场景，收集所有候选对象：

````
def _iter_json_candidates(content: str) -> list[Any]:
    decoder = json.JSONDecoder()
    candidates: list[Any] = []
    idx = 0
    while idx < len(content):
        while idx < len(content) and content[idx].isspace():
            idx += 1
        if idx >= len(content):
            break
        try:
            payload, end = decoder.raw_decode(content, idx)
        except json.JSONDecodeError:
            idx += 1
            continue
        candidates.append(payload)
        idx = end
    return candidates
````

2. 按业务字段打分筛选

根据项目核心字段（focus_points、questions、personal_info）设计打分规则，同时直接屏蔽模板类内容：

````
def _score_json_candidate(payload: Any) -> int:
    if not isinstance(payload, dict):
        return 0
    score = 1
    if _looks_like_prompt_template(payload):
        return 0
    focus_points = payload.get("focus_points")
    if isinstance(focus_points, list) and focus_points:
        score += 10 + len(focus_points)
    questions = payload.get("questions")
    if isinstance(questions, list) and questions:
        score += 20 + len(questions)
    if payload.get("personal_info") is not None:
        score += 15
    return score
````

3. 整合进提取主流程

汇总候选内容后，自动选出得分最高的结果，无合格数据再走传统兜底逻辑：

````
def _extract_json(text: str) -> Any:
    content = (text or "").strip()
    # ... 剥离 markdown ...
    candidates = _iter_json_candidates(content)
    if candidates:
        best = max(candidates, key=_score_json_candidate)
        if _score_json_candidate(best) > 0:
            return best
    # 回退 json.loads / 正则 ...
````

如果 LLM 只输出了一个 JSON，候选列表只有一个元素，打分逻辑同样生效，只是没有竞争者而已。

#### 拦截模板占位内容：echo-back 检测

echo-back 是指：LLM 输出的 JSON 字段名和结构都完全正确，但字段的值不是真实数据，而是 prompt 里写的格式说明和占位符，无法用于业务。

比如 prompt 里有这样一段：

````
请返回 JSON，格式如下：
{
  "focus_points": ["最多4个考察焦点"],
  "questions": [{"id": "q1", "title": "题目标题", "prompt": "题目内容", ...}]
}
````

发生 echo-back 时，LLM 的回复几乎就是把这段格式说明原封不动地返回：

````
{
  "focus_points": ["最多4个考察焦点"],
  "questions": [{"id": "q1", "title": "题目标题", "prompt": "题目内容", ...}]
}
````

这份模板 JSON 语法完全合规。如果文本中存在多个 JSON 片段，打分机制会将模板内容记为 0 分，从而完成过滤。可倘若全文仅有这一份模板 JSON，由于没有其他候选作对比，打分筛选就会失效，程序会进入最后的兜底解析流程，误将无效模板当作正常业务数据。

因此项目做了两道防线：

1. 提取层：打分函数中调用该检测，模板类 JSON 直接计 0 分，优先被淘汰；

2. 业务层：拿到解析结果后再次校验，一旦命中模板，自动回退到本地规则链路：

````
payload = client.generate_json(prompt, ...)
if not isinstance(payload, dict) or _looks_like_prompt_template(payload):
    return fallback_focus_points, adapt_question_difficulty(
        build_questions(target_role, fallback_focus_points), difficulty_level
    )
````

##### 为什么会发生

出现 echo-back，大多是提示词设计导致：模型在低温度配置下输出偏保守，会直接复制提示词内的格式模板作为答案。从源头优化提示词，可大幅降低该问题概率：

1. 区分示例与说明：不要将格式描述、占位符和正式示例混写；

````
# 不好的写法
输出格式：{"title": "题目标题", "content": "题目内容"}

# 好的写法
以下是一个输出示例，注意 title 和 content 都应该是真实内容：
{"title": "Redis 的 SETNX 命令", "content": "解释 SETNX 的原子性及使用场景"}
````

2. 使用真实样例：示例内容采用业务真实数据，而非通用占位文字；

3. 明确约束要求：在提示词中注明「禁止输出格式说明，仅返回真实业务数据」。

#### 保障提取逻辑稳定性：自动化测试

JSON 提取的异常场景相对固定，非常适合编写自动化用例，我们可以借助 AI 快速生成测试代码，再人工校对补充。

给 AI 的 prompt 可以这样写：

````
我有一个函数 _extract_json(text: str)，用于从 LLM 输出中提取 JSON。

已知的失败模式有：
1. 输出包含 markdown 代码块（```json ... ```）
2. 输出了多个 JSON 对象，需要选字段命中得分最高的那个
3. 输出前后有多余的自然语言说明
4. LLM 回吐了 prompt 模板（echo-back），字段值是占位符

请为这个函数生成 pytest 测试用例，每种失败模式至少覆盖一个成功案例和一个边界案例。
````

AI 大概会生成这样的测试：

````
import pytest
from app.llm.factory import _extract_json, _looks_like_prompt_template

# 测试剥离Markdown代码块
def test_strips_markdown_code_block():
    text = '```json\n{"focus_points": ["Redis缓存"], "questions": [{"id": "q1", "title": "题目", "prompt": "请描述...", "focus": "缓存", "follow_up_hint": "继续"}]}\n```'
    result = _extract_json(text)
    assert "questions" in result

# 测试多JSON择优筛选
def test_picks_highest_scoring_candidate():
    text = '''
    附加说明：{"max_score": 10, "dimensions": ["正确性"]}
    面试计划：{"focus_points": ["系统设计"], "questions": [{"id": "q1", "title": "分布式锁", "prompt": "请描述实现方式", "focus": "Redis", "follow_up_hint": "继续追问"}]}
    '''
    result = _extract_json(text)
    assert "focus_points" in result
    assert "questions" in result

# 测试识别echo-back模板
def test_echo_back_detected_by_template_checker():
    payload = {"focus_points": ["最多4个考察焦点"], "questions": [{"title": "题目标题", "prompt": "题目内容"}]}
    assert _looks_like_prompt_template(payload) is True
````

持续补充测试用例有两大价值：一是修改提取逻辑后，可快速验证是否破坏原有能力；二是 AI 能协助挖掘嵌套 JSON 等人工易忽略的边界场景。

#### JSON 提取逻辑迭代原则

没有一个通用标准说"这段 JSON 提取代码足够了"。实践中的判断标准很简单：能覆盖你自己测试集里的所有失败案例时，就够用了。

1. 从线上日志积累样本：解析失败时留存原始输出，将新异常场景补充为测试用例，再迭代代码修复；

2. 区分问题根源：如果输出完全无 JSON 结构、彻底失序，不必继续堆砌提取逻辑，优先优化提示词；

3. 把控边界：提取代码的核心是「兜底容错」，格式规范的源头仍依赖提示词引导。

整套方案遵循「基础提取→多候选筛选→模板拦截→自动化校验」的完整链路，层层加固，能有效应对 LLM 输出的各类格式异常，保障 AI Agent 链路稳定运行。