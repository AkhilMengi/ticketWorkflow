from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from app.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class JobRecord(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False)
    input_payload = Column(Text, nullable=True)
    result_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class EventRecord(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class MemoryRecord(Base):
    __tablename__ = "memory"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, index=True)
    memory_type = Column(String, nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)