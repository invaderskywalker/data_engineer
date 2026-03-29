from sqlalchemy import Column, Integer, Text, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import Base


# =========================
# Agent Run Steps
# =========================
class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Text, nullable=False)
    tenant_id = Column(Text, nullable=False)
    user_id = Column(Text, nullable=False)
    agent_name = Column(Text)
    run_id = Column(Text, nullable=False)
    step_type = Column(Text, nullable=False)
    step_index = Column(Integer, nullable=False, default=0)
    step_payload = Column(JSONB)
    status = Column(Text, nullable=False, default="completed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# Agent Run Events
# =========================
class AgentRunEvent(Base):
    __tablename__ = "agent_run_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Text, nullable=False)
    step_id = Column(Integer)
    parent_event_id = Column(Integer)
    event_type = Column(Text, nullable=False)
    event_name = Column(Text)
    sequence_index = Column(Integer, nullable=False, default=0)
    local_index = Column(Integer)
    event_payload = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# Tango State
# =========================
class TangoState(Base):
    __tablename__ = "tango_states"

    id = Column(Text, primary_key=True)
    tenant_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    session_id = Column(Text)
    key = Column(Text, nullable=False)
    value = Column(Text)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# Conversations
# =========================
class TangoConversation(Base):
    __tablename__ = "tango_tangoconversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Text, nullable=False)
    tenant_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    role = Column(Text, nullable=False)
    message = Column(Text)
    metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# Chat Titles
# =========================
class TangoChatTitle(Base):
    __tablename__ = "tango_chattitles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Text, nullable=False, unique=True)
    tenant_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    agent_name = Column(Text)
    title = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# Stats
# =========================
class TangoStat(Base):
    __tablename__ = "tango_stats"

    id = Column(Text, primary_key=True)
    user_id = Column(Integer, nullable=False)
    tenant_id = Column(Integer, nullable=False)
    function = Column(Text)
    model = Column(Text)
    total_tokens = Column(Integer, default=0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    created_date = Column(DateTime(timezone=True), server_default=func.now())


# =========================
# Activity Log
# =========================
class TangoActivityLog(Base):
    __tablename__ = "tango_activitylog"

    id = Column(Text, primary_key=True)
    session_id = Column(Text, nullable=False)
    tenant_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    activity_name = Column(Text)
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    status = Column(Text, default="completed")
    created_date = Column(DateTime(timezone=True), server_default=func.now())
    