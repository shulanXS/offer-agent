"""Interview Reply LangGraph（05 小步 2：Evidence Extraction）。"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agent.interview.nodes.act_probe import act_probe_node
from app.agent.interview.nodes.boundaries import enforce_boundaries_node
from app.agent.interview.nodes.decide_node import decide_node
from app.agent.interview.nodes.extract_evidence import extract_evidence_node
from app.agent.interview.nodes.finalize import finalize_advance_node, finalize_forced_finish_node
from app.agent.interview.nodes.ingest import ingest_answer_node
from app.agent.interview.nodes.merge_working_memory import merge_working_memory_node
from app.agent.interview.nodes.observe import build_observe_node
from app.agent.interview.nodes.prepare_repeat_blocked import prepare_repeat_blocked_node
from app.agent.interview.routing import route_after_boundary, route_after_decide
from app.agent.interview.state import InterviewReplyState


_builder = StateGraph(InterviewReplyState)

_builder.add_node("ingest_answer", ingest_answer_node)
_builder.add_node("build_observe", build_observe_node)
_builder.add_node("enforce_boundaries", enforce_boundaries_node)
_builder.add_node("extract_evidence", extract_evidence_node)
_builder.add_node("merge_working_memory", merge_working_memory_node)
_builder.add_node("decide", decide_node)
_builder.add_node("prepare_repeat_blocked", prepare_repeat_blocked_node)
_builder.add_node("act_probe", act_probe_node)
_builder.add_node("finalize_advance", finalize_advance_node)
_builder.add_node("finalize_forced_finish", finalize_forced_finish_node)

_builder.add_edge(START, "ingest_answer")
_builder.add_edge("ingest_answer", "build_observe")
_builder.add_edge("build_observe", "enforce_boundaries")
_builder.add_conditional_edges(
    "enforce_boundaries",
    route_after_boundary,
    {
        "finish": "finalize_forced_finish",
        "next_topic": "finalize_advance",
        "continue": "extract_evidence",
    },
)
_builder.add_edge("extract_evidence", "merge_working_memory")
_builder.add_edge("merge_working_memory", "decide")
_builder.add_conditional_edges(
    "decide",
    route_after_decide,
    {
        "probe": "act_probe",
        "repeat_blocked": "prepare_repeat_blocked",
        "advance": "finalize_advance",
    },
)
_builder.add_edge("prepare_repeat_blocked", "finalize_advance")
_builder.add_edge("act_probe", END)
_builder.add_edge("finalize_advance", END)
_builder.add_edge("finalize_forced_finish", END)

interview_reply_graph = _builder.compile()
