"""域 1.4 验证：硬边界预检不写 user_message。"""
from __future__ import annotations

import importlib
import json
import time
import uuid

import pytest

from app.db import store as store_mod
from app.db import transaction as tx_mod
from app.db.transaction import transaction


@pytest.fixture
def fresh_db(monkeypatch, tmp_path):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    from app.core import config as cfg
    monkeypatch.setattr(cfg.settings, "database_path", db_file)
    importlib.reload(store_mod)
    importlib.reload(tx_mod)
    from app.services import interview_agent_service as svc_mod
    importlib.reload(svc_mod)
    store_mod.init_db()
    yield db_file, svc_mod


def test_precheck_boundary_skips_user_message(fresh_db, monkeypatch) -> None:
    _db_file, svc_mod = fresh_db
    # 锁定 topic_round 上限=1，第二次 ingest 直接命中
    monkeypatch.setattr("app.services.interview.boundaries.MAX_TOPIC_ANSWER_ROUNDS", 1)
    monkeypatch.setattr("app.services.interview.boundaries.MAX_TOPIC_PROBE_COUNT", 99)

    user_id = int(time.time() * 1000) % 1_000_000 + 1
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, password_hash, quota_remaining, created_at, updated_at)
            VALUES (?, ?, 'h', 5, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """,
            (user_id, f"u_{user_id}"),
        )
    sid = str(uuid.uuid4())
    plan_id = str(uuid.uuid4())
    ts = "2026-01-01T00:00:00+00:00"
    plan_json = {
        "topics": [
            {"id": "t1", "name": "Topic 1", "required": True},
            {"id": "t2", "name": "Topic 2", "required": True},
            {"id": "t3", "name": "Topic 3", "required": True},
            {"id": "t4", "name": "Topic 4", "required": True},
            {"id": "t5", "name": "Topic 5", "required": True},
        ]
    }
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO interview_sessions
                (id, user_id, title, target_role, status, profile_json,
                 workflow_state_json, evaluation_json, resume_id, configuration_json,
                 confirmed_plan_id, version, created_at, updated_at)
            VALUES (?, ?, 'demo', 'backend', 'plan_confirmed', ?, '{}', NULL, NULL, ?, ?, 0, ?, ?)
            """,
            (
                sid, user_id,
                '{"schema_version": 2, "configuration": {"interview_type": "experienced"}}',
                '{"interview_type": "experienced"}',
                plan_id, ts, ts,
            ),
        )
        conn.execute(
            """
            INSERT INTO interview_plans
                (id, session_id, version, status, plan_json, candidate_summary_json, created_at)
            VALUES (?, ?, 1, 'confirmed', ?, '{}', ?)
            """,
            (plan_id, sid, json.dumps(plan_json), ts),
        )

    svc = svc_mod.InterviewAgentService()
    # 激活（扣 quota + 写 opening）
    svc.activate_interview(user_id, sid)
    # 4 个非末尾 topic 各打 1 次 → 命中 topic_round_limit，路由到 next_topic（不删 user）。
    for i in range(4):
        svc.reply_to_interview(user_id, sid, f"answer {i+1}")
    record = store_mod.Store().get_interview_session_record(user_id, sid)
    user_count_before = sum(1 for m in record["messages"] if m["role"] == "user")
    # activate 写 0 个 user；r1..r4 各写 1 个 user → 4
    assert user_count_before == 4
    # 末尾 topic 第 1 次 reply 命中 topic_round_limit_last_topic → finish。
    # service 在 finish 路径上应回滚刚写的 user_message。
    svc.reply_to_interview(user_id, sid, "final answer that should be skipped")
    record = store_mod.Store().get_interview_session_record(user_id, sid)
    user_count_after = sum(1 for m in record["messages"] if m["role"] == "user")
    # 关键断言：user 消息数仍为 4，没增长
    assert user_count_after == 4
    # session 应已进入 evaluating 或 finished 状态
    assert record["status"] in {"evaluating", "finished"}
