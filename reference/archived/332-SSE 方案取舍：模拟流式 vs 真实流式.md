# SSE 方案取舍：模拟流式 vs 真实流式

目录路径：实战项目 / AI面试智能体 / V1 版本开发 / 核心难点 / SSE 方案取舍：模拟流式 vs 真实流式

[原页面](https://acn2lw4rwc26.feishu.cn/wiki/NBRdwyh8yiSCCIkoRkHcf7PfnVd)

如今绝大多数 AI 产品的对话回复，都会采用逐字输出的流式效果，这种体验依托 SSE（服务器推送事件） 实现，能让用户直观感受到模型 “实时生成内容”，远比等待全文一次性返回更友好。

但 SSE 流式输出有两种实现方式，背后的机制完全不同。一种是真实的 token 流，AI 每生成一个 token 就立刻推送给前端；另一种是先等 AI 跑完，拿到完整响应，再分块模拟出流式的效果。offer-agent 选择了后者。为什么？这篇文章讲清楚这两种方案的差异和取舍。

#### 两种方案对比

先看一张图，建立整体认知：

![页面图片](../assets/332-e53a385044c53471.png)

TTFB 是 Time To First Byte 的缩写，指用户看到第一个字之前需要等多久。真实流式的 TTFB 只有 AI 生成第一个 token 的时间，可能不到一秒。模拟流式的 TTFB 是 AI 生成完整响应的时间，比如 3 到 5 秒。

结合本项目面试评价的业务场景，单条回复大多不足 200 字，几秒的等待不会影响使用体验，模拟流式在体验上完全可以满足要求。

除此之外，项目基于 LangGraph 搭建流程，也让真实流式的落地变得复杂：

1. LangGraph 由多个节点串联而成，执行 invoke 时会跑完全部节点，中途无法提前推送内容；

2. 框架虽支持流式模式，但会同步返回所有节点的中间状态，需要额外筛选、过滤，只对外推送最终业务内容；

3. 还要兼容异步生成器串联、异常捕获、请求主动取消等边界场景。

![页面图片](../assets/332-5d789f2af63fcf55.png)

综合体验、架构复杂度两大因素，项目初期选择模拟流式是更务实的方案，既能快速落地、简化架构，也完全匹配短文本输出的场景。后续如果业务拓展出长文本需求，或是对首字延迟有更高要求，再逐步迁移到真实 token 流即可。

#### 模拟流式完整实现

模拟流式依靠两组核心函数配合完成：stream_text 负责文本分块与延时推送，format_sse 负责按照 SSE 协议封装消息。

1. 基础工具函数

format_sse 支持自定义事件名，前端可按事件类型单独监听处理，无需统一解析消息内容：

````
def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

````

stream_text 会按照配置切割文本，并添加固定间隔，模拟逐字输出效果：

````
async def stream_text(text: str) -> AsyncIterator[str]:
    """预先计算好完整响应，然后分块流出（纯文本块，不含 SSE 格式）"""
    for chunk in chunk_text(text):   # chunk_text 按 settings.stream_chunk_size 切分
        yield chunk
        await asyncio.sleep(settings.stream_delay_ms / 1000)
````

代码中使用 await asyncio.sleep() 不会阻塞服务器。它是协程休眠，执行时会暂时挂起当前任务，将资源交还给事件循环，服务器可同时处理其他请求。 只有 time.sleep() 才会阻塞整个线程，这也是异步框架的基础特性。

2. 业务层组装流式消息

在上层服务中串联各类事件，依次推送开始、内容、附加信息、结束等消息：

````
async def stream_reply_result(self, payload: dict) -> Any:
    assistant_message = payload["assistant_message"]
    # 推送会话开始事件
    yield format_sse("message_start", {"session_id": ..., "message": assistant_message})
    # 循环推送文本分片
    async for chunk in stream_text(assistant_message["content"]):
        yield format_sse("delta", {"message_id": assistant_message["id"], "delta": chunk})
    # 推送消息结束、评价、会话完成等事件
    yield format_sse("message_end", {"message": assistant_message})
    if payload.get("evaluation"):
        yield format_sse("evaluation", {"evaluation": payload["evaluation"]})
    yield format_sse("done", {"status": ..., "session_id": ...})
````

chunk 大小和延迟通过 settings 配置：

````
STREAM_CHUNK_SIZE=10   # 每次推送的字符数，默认 10
STREAM_DELAY_MS=25     # 推送间隔毫秒，默认 25
````

3. 在 FastAPI 里接入

模拟流式接入 FastAPI 的方式很标准：

````
from fastapi.responses import StreamingResponse

@router.post("/{session_id}/reply/stream")
async def reply_interview_stream(session_id: str, request: ReplyInterviewRequest, ...) -> StreamingResponse:
    # 先获取完整结果，再交由流式函数处理
    result = service.reply_to_interview(current_user["id"], session_id, request.content)
    return StreamingResponse(
        service.stream_reply_result(result),
        media_type="text/event-stream",
    )
````

缓存、Nginx 缓冲等相关头部配置，统一在网关层设置，业务接口无需额外处理。

#### 选型结论

模拟流式并非妥协方案，而是结合项目场景做出的合理选择。回复短、架构简单、LangGraph 集成容易，这些优势在 MVP 阶段比低延迟更重要。

等用户规模增长、或者场景扩展到需要生成长文本的情况，再切真实 token 流，是清晰的演进路径。