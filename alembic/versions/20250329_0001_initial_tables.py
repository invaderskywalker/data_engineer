"""Initial tables for AI data engineer

Revision ID: 0001
Revises:
Create Date: 2025-03-29

Tables created:
  - agent_run_steps     : one row per LLM step inside a super-agent run
  - agent_run_events    : granular events (thoughts, actions) within a step
  - tango_states        : persistent key/value session state per user
  - tango_tangoconversations : full conversation message history
  - tango_chattitles    : auto-generated session titles shown in the sidebar
  - tango_stats         : token usage per LLM call
  - tango_activitylog   : high-level activity log (input/output pairs)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ─────────────────────────────────────────────────────────────
    # agent_run_steps
    # One row per logical step that the super-agent executed.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "agent_run_steps",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("agent_name", sa.Text, nullable=True),
        sa.Column("run_id", sa.Text, nullable=False),
        sa.Column("step_type", sa.Text, nullable=False),
        sa.Column("step_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("step_payload", JSONB, nullable=True),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default="completed",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_agent_run_steps_run_id", "agent_run_steps", ["run_id"])
    op.create_index("ix_agent_run_steps_session_id", "agent_run_steps", ["session_id"])
    op.create_index(
        "ix_agent_run_steps_tenant_user",
        "agent_run_steps",
        ["tenant_id", "user_id"],
    )

    # ─────────────────────────────────────────────────────────────
    # agent_run_events
    # Fine-grained events within a step: thoughts, action calls,
    # action results, etc.  Supports recursive trees via parent_event_id.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "agent_run_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Text, nullable=False),
        sa.Column("step_id", sa.Integer, nullable=True),
        sa.Column("parent_event_id", sa.Integer, nullable=True),
        sa.Column("event_type", sa.Text, nullable=False),   # thought | action | action_result | step_update
        sa.Column("event_name", sa.Text, nullable=True),
        sa.Column("sequence_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("local_index", sa.Integer, nullable=True),
        sa.Column("event_payload", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_agent_run_events_run_id", "agent_run_events", ["run_id"])
    op.create_index("ix_agent_run_events_step_id", "agent_run_events", ["step_id"])

    # ─────────────────────────────────────────────────────────────
    # tango_states
    # Generic key/value store scoped to tenant + user + session.
    # Used to persist agent memory across socket reconnects.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "tango_states",
        sa.Column("id", sa.Text, primary_key=True),        # UUID string
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("session_id", sa.Text, nullable=True),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column(
            "created_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_tango_states_session_key", "tango_states", ["session_id", "key"])
    op.create_index("ix_tango_states_tenant_user", "tango_states", ["tenant_id", "user_id"])

    # ─────────────────────────────────────────────────────────────
    # tango_tangoconversations
    # Full conversation history: every user message and assistant reply.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "tango_tangoconversations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("role", sa.Text, nullable=False),         # user | assistant | system
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_tango_conversations_session",
        "tango_tangoconversations",
        ["session_id"],
    )

    # ─────────────────────────────────────────────────────────────
    # tango_chattitles
    # Auto-generated title for each chat session (shown in sidebar).
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "tango_chattitles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text, nullable=False, unique=True),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("agent_name", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_tango_chattitles_user", "tango_chattitles", ["user_id", "tenant_id"])

    # ─────────────────────────────────────────────────────────────
    # tango_stats
    # Token usage per LLM call — for cost tracking and monitoring.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "tango_stats",
        sa.Column("id", sa.Text, primary_key=True),        # UUID string
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("function", sa.Text, nullable=True),
        sa.Column("model", sa.Text, nullable=True),
        sa.Column("total_tokens", sa.Integer, nullable=True, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer, nullable=True, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=True, server_default="0"),
        sa.Column(
            "created_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # ─────────────────────────────────────────────────────────────
    # tango_activitylog
    # High-level log of what the agent did: input + output pairs.
    # ─────────────────────────────────────────────────────────────
    op.create_table(
        "tango_activitylog",
        sa.Column("id", sa.Text, primary_key=True),        # UUID string
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("tenant_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("activity_name", sa.Text, nullable=True),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("status", sa.Text, nullable=True, server_default="completed"),
        sa.Column(
            "created_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_tango_activitylog_session", "tango_activitylog", ["session_id"])


def downgrade() -> None:
    op.drop_table("tango_activitylog")
    op.drop_table("tango_stats")
    op.drop_table("tango_chattitles")
    op.drop_table("tango_tangoconversations")
    op.drop_table("tango_states")
    op.drop_table("agent_run_events")
    op.drop_table("agent_run_steps")
