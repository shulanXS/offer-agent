#!/usr/bin/env bash
# v2.3 根因修复后端验证脚本
# - 跑所有新增 + 关键现有测试
# - 覆盖：subscription 状态机 / 评估锁 / interview_language / 算法错误码 / reply 幂等
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"

echo "[v2.3 verify] start"

# 1) 数据库 store 单测
echo "[v2.3 verify] 1/4 idempotent + session_locks"
$PYTHON -m pytest tests/test_idempotent_reply_v23.py -x -q

# 2) billing subscription v2.3
echo "[v2.3 verify] 2/4 billing subscription"
$PYTHON -m pytest tests/test_billing_subscription_v23.py -x -q

# 3) 评估锁 + SSE
echo "[v2.3 verify] 3/4 evaluation lock + SSE event"
$PYTHON -m pytest tests/test_evaluation_lock_v23.py -x -q

# 4) interview_language + 算法错误码
echo "[v2.3 verify] 4/4 interview_language + algo"
$PYTHON -m pytest tests/test_request_validation_v23.py tests/test_algorithm_judge_v23.py -x -q

echo "[v2.3 verify] OK"
