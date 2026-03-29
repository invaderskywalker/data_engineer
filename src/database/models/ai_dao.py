from sqlalchemy import Column, Integer, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from .base import Base


class DAOAttribute(Base):
    __tablename__ = "dao_attributes"

    id = Column(Integer, primary_key=True, autoincrement=True)

    entity_type = Column(Text, nullable=False)   # project, roadmap
    attr_name = Column(Text, nullable=False)     # core, milestones

    table_name = Column(Text, nullable=False)
    table_alias = Column(Text, nullable=False)

    description = Column(Text)

    id_field = Column(Text, default="project_id")

    base_where = Column(JSONB)   # ["wp.tenant_id_id = %s"]
    where_extra = Column(Text)

    joins = Column(JSONB)        # ["LEFT JOIN ..."]

    group_by = Column(Text)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class DAOField(Base):
    __tablename__ = "dao_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)

    attr_id = Column(Integer, ForeignKey("dao_attributes.id"), nullable=False)

    field_name = Column(Text, nullable=False)
    sql_expression = Column(Text, nullable=False)

    is_default = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DAOFieldIntel(Base):
    __tablename__ = "dao_field_intel"

    id = Column(Integer, primary_key=True, autoincrement=True)

    attr_id = Column(Integer, ForeignKey("dao_attributes.id"), nullable=False)

    field_name = Column(Text, nullable=False)

    type = Column(Text)          # enum, text, number, date, pii_text
    column_name = Column(Text)

    mapping = Column(JSONB)      # enum mapping
    extra = Column(JSONB)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DAOAttributeHook(Base):
    __tablename__ = "dao_attribute_hooks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    attr_id = Column(Integer, ForeignKey("dao_attributes.id"))

    hook_type = Column(Text)   # pre_filter, post_process
    hook_name = Column(Text)   # e.g. "handle_archive_logic"

    config = Column(JSONB)

    