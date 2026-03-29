import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ✅ IMPORT BASE + MODELS (VERY IMPORTANT)
from src.database.models.base import Base
from src.database.models import *  # ensures models are registered

# ✅ REQUIRED FOR AUTOGENERATE
target_metadata = Base.metadata


# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ✅ FIXED DB URL (handles empty password)
def get_url() -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    if not name or not user:
        raise ValueError("Missing required DB env vars: DB_NAME, DB_USER")

    # handle local DB without password
    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    else:
        return f"postgresql://{user}@{host}:{port}/{name}"


def run_migrations_offline() -> None:
    """Run migrations without DB connection"""
    url = get_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,   # ✅ REQUIRED
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with live DB"""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,   # ✅ REQUIRED
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
    