"""Alembic 环境配置：使用项目内 SQLite 路径。

自动调用 `app.db.store.init_db()` 创建表结构（idempotent CREATE TABLE IF NOT EXISTS），
再走 alembic 增量迁移（补 v2.1 新增的列和表）。
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 允许通过环境变量覆盖 database_path
db_path = os.environ.get("ALEMBIC_DATABASE_PATH", "./data/offer_agent.db")
config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

target_metadata = None  # 项目目前以手工建表为主，不引入 ORM metadata

_BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # 1) 先确保表结构已存在（init_db 是 idempotent CREATE TABLE IF NOT EXISTS）
    sys.path.insert(0, str(_BACKEND_DIR))
    # 若 ALEMBIC_DATABASE_PATH 存在，覆盖 settings.database_path 以走 init_db 路径
    from app.core import config as _cfg
    from app.db.store import init_db as _init_db

    if "ALEMBIC_DATABASE_PATH" in os.environ:
        _cfg.settings.database_path = os.environ["ALEMBIC_DATABASE_PATH"]
    _init_db()

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
