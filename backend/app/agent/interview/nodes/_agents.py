"""图节点共享 Agent 实例。"""
from __future__ import annotations

from app.agent.interview.act import InterviewActAgent
from app.agent.interview.decide import InterviewDecideAgent


decide_agent = InterviewDecideAgent()
act_agent = InterviewActAgent()
