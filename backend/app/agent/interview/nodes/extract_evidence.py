"""Evidence Extraction 图节点。"""
from __future__ import annotations

from app.agent.interview.evidence.extract import InterviewEvidenceExtractor
from app.agent.interview.state import InterviewReplyState
from app.services.interview.memory.schema import ensure_working_memory


_extractor = InterviewEvidenceExtractor()


def extract_evidence_node(state: InterviewReplyState) -> InterviewReplyState:
    runtime_state = state["runtime_state"]
    working_memory = ensure_working_memory(runtime_state)
    extraction, _stats = _extractor.extract(
        current_topic=state["current_topic"],
        plan_json=state["plan_json"],
        topic_messages=state.get("topic_messages") or [],
        topic_summaries=runtime_state.get("topic_summaries") or {},
        latest_answer=state["latest_answer"],
        working_memory=working_memory,
        trace_id=state.get("trace_id", ""),
    )
    return {**state, "extraction_result": extraction}
