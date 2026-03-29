from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class TestTableOne(Base):
    __tablename__ = 'test_table_one'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

class TestTableTwo(Base):
    __tablename__ = 'test_table_two'
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(String(256), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
