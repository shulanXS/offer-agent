"""域 2.2 验证：evidence 句级匹配。"""
from __future__ import annotations

from app.services.interview.memory.extraction_schema import (
    _content_grounded_in_answer,
    quote_in_latest_answer,
)


def test_quote_完整在句内_passes() -> None:
    answer = "我做过 Kafka。设计过电商秒杀系统。用过 Redis。"
    assert quote_in_latest_answer("设计过电商秒杀系统", answer) is True


def test_quote_跨句被拒() -> None:
    answer = "我做过 Kafka；设计过电商秒杀系统，并发十万。"
    # 该 quote 包含两个句子之间被截断的字符
    assert quote_in_latest_answer("Kafka；设计过电商", answer) is False


def test_quote_部分在中段被拒() -> None:
    answer = "我从前端转岗到后端，后来做过秒杀系统，最后做推荐。"
    # 这串中段字符在 answer 中存在，但必须完整出现于某一句内
    assert quote_in_latest_answer("后端，后来做过秒杀系统", answer) is True
    assert quote_in_latest_answer("做推荐", answer) is True
    # 半句话中段不应被命中
    assert quote_in_latest_answer("后端后来做过秒杀", answer) is False


def test_content_grounded_in_answer_sentence() -> None:
    answer = "We built a high-throughput system. Latency dropped by 30%. Customers were happy."
    # 完整句级
    assert _content_grounded_in_answer("Latency dropped by 30%", answer) is True
    # 跨句拼接被拒
    assert _content_grounded_in_answer("system. Latency", answer) is False


def test_sentence_cache_ttl() -> None:
    """切句缓存 1 秒。"""
    from app.services.interview.memory.extraction_schema import _cached_sentences

    answer = "A. B. C."
    s1 = _cached_sentences(answer)
    # 立即再切应复用缓存
    s2 = _cached_sentences(answer)
    assert s1 is s2
    # 强制过期
    from app.services.interview.memory import extraction_schema as mod
    mod._SENTENCE_CACHE.clear()
    s3 = _cached_sentences(answer)
    assert s3 == ["A", "B", "C"]
