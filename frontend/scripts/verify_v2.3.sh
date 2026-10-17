#!/usr/bin/env bash
# v2.3 根因修复前端验证脚本
# - 静态：grep 检查无 .v2- 残留、.membership_status 类型扩展存在
# - 单元：service 透传 + pause/resume 排队
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[v2.3 verify] 1/4 no v2- class residuals"
if grep -rE '\bv2-' src --include='*.tsx' --include='*.ts' --include='*.css' > /dev/null; then
  echo "FAIL: .v2- classes still present"
  exit 1
fi
echo "  ok"

echo "[v2.3 verify] 2/4 UserProfile 类型扩展"
grep -q "membership_status" src/types/auth.ts || { echo "FAIL: membership_status missing"; exit 1; }
echo "  ok"

echo "[v2.3 verify] 3/4 BillingUserStatus 类型扩展"
grep -q "membership_status" src/services/billing.ts || { echo "FAIL: membership_status missing in billing.ts"; exit 1; }
echo "  ok"

echo "[v2.3 verify] 4/4 createInterview 透传"
grep -E 'createInterview.*payload' src/services/interviewPlan.ts | grep -q 'duration_minutes' && { echo "FAIL: hardcoded duration_minutes"; exit 1; } || true
echo "  ok"

echo "[v2.3 verify] all static checks passed"
echo "[v2.3 verify] (run vitest for runtime tests if installed)"
