"""域 4.3 验证：alembic 迁移幂等且能成功。"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run_alembic(args: list[str], db_path: str, cwd: Path) -> tuple[int, str]:
    """运行 alembic 子命令并合并 stdout+stderr 返回。"""
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_PATH"] = db_path
    env["DATABASE_PATH"] = db_path  # 覆盖 settings.database_path 以走 init_db 路径
    result = subprocess.run(
        [".venv/bin/alembic", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, result.stdout + result.stderr


def test_alembic_upgrade_head_fresh_db(tmp_path: Path) -> None:
    """空 DB 上 alembic upgrade head 成功。"""
    db_path = str(tmp_path / "alembic_fresh.db")
    if os.path.exists(db_path):
        os.unlink(db_path)
    backend_dir = Path(__file__).resolve().parents[1]
    rc, out = _run_alembic(["upgrade", "head"], db_path, backend_dir)
    assert rc == 0, f"alembic failed: {out}"
    assert "v2_1_initial" in out


def test_alembic_upgrade_idempotent(tmp_path: Path) -> None:
    """已升级 DB 上再次 upgrade 应幂等（不抛错）。"""
    db_path = str(tmp_path / "alembic_idem.db")
    if os.path.exists(db_path):
        os.unlink(db_path)
    backend_dir = Path(__file__).resolve().parents[1]
    rc1, _ = _run_alembic(["upgrade", "head"], db_path, backend_dir)
    assert rc1 == 0
    rc2, out2 = _run_alembic(["upgrade", "head"], db_path, backend_dir)
    assert rc2 == 0
    # 第二次应没有"Running upgrade"输出（因为已是 head）
    assert "Running upgrade" not in out2


def test_alembic_current(tmp_path: Path) -> None:
    """alembic current 能正确显示当前版本。"""
    db_path = str(tmp_path / "alembic_current.db")
    if os.path.exists(db_path):
        os.unlink(db_path)
    backend_dir = Path(__file__).resolve().parents[1]
    _run_alembic(["upgrade", "head"], db_path, backend_dir)
    rc, out = _run_alembic(["current"], db_path, backend_dir)
    assert rc == 0
    assert "v2_1_initial" in out
