from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from .base import Base


class DEConnection(Base):
    __tablename__ = "de_connections"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    host = Column(Text, nullable=False)        # stored encrypted
    port = Column(Integer, nullable=False, default=5432)
    database = Column(Text, nullable=False)
    username = Column(Text, nullable=False)    # stored encrypted
    password = Column(Text, nullable=False)    # stored encrypted
    ssl = Column(Boolean, nullable=False, default=True)
    status = Column(Text, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_connected_at = Column(DateTime(timezone=True), nullable=True)


class DESchemaSnapshot(Base):
    __tablename__ = "de_schema_snapshots"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    connection_id = Column(UUID(as_uuid=False), ForeignKey("de_connections.id", ondelete="CASCADE"), nullable=False)
    schema_json = Column(JSONB, nullable=False)
    semantic_layer = Column(JSONB, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DESession(Base):
    __tablename__ = "de_sessions"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(Text, nullable=False)
    connection_id = Column(UUID(as_uuid=False), ForeignKey("de_connections.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), server_default=func.now())


class DERun(Base):
    __tablename__ = "de_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(UUID(as_uuid=False), ForeignKey("de_sessions.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(UUID(as_uuid=False), ForeignKey("de_connections.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)
    queries_executed = Column(JSONB, nullable=True)   # [{sql, rows_returned, execution_time_ms}]
    table_data = Column(JSONB, nullable=True)          # {columns, rows}
    chart_spec = Column(JSONB, nullable=True)          # {type, title, x_axis, y_axis, data}
    sheet_s3_key = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
