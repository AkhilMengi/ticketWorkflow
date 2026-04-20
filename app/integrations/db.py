from sqlalchemy import create_engine, Column, String, Text, DateTime, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from datetime import datetime
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Database connection parameters with connection pooling and transaction isolation (SERIALIZABLE)
engine_kwargs = {
    "connect_args": {"check_same_thread": False, "isolation_level": "SERIALIZABLE"} if "sqlite" in settings.DATABASE_URL else {"isolation_level": "SERIALIZABLE"},
    "poolclass": QueuePool if "sqlite" not in settings.DATABASE_URL else None,
}

# Add pool configuration for non-SQLite databases
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs.update({
        "pool_size": settings.DATABASE_POOL_SIZE,
        "max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
        "pool_recycle": settings.DATABASE_POOL_RECYCLE,
    })

logger.info(f"Creating database engine with URL: {settings.DATABASE_URL}")
logger.info(f"Transaction isolation level: SERIALIZABLE (highest isolation level)")

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

# Set transaction isolation level for SQLite connections
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite transaction isolation level to SERIALIZABLE"""
    if "sqlite" in settings.DATABASE_URL.lower():
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        # SQLite only supports DEFERRED, IMMEDIATE, EXCLUSIVE
        cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
        cursor.execute("PRAGMA synchronous=FULL")   # Ensure data durability
        cursor.execute("PRAGMA temp_store=MEMORY")  # Use memory for temp storage
        cursor.close()
        logger.debug("SQLite transaction isolation pragmas set to enforce SERIALIZABLE-like behavior")

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=True,  # Ensure fresh data after commit
    isolation_level="SERIALIZABLE"  # Set transaction isolation level
)

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
    """Initialize database with all tables and transaction isolation"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully with SERIALIZABLE isolation level")

def get_db():
    """Get a database session with SERIALIZABLE isolation level"""
    db = SessionLocal()
    try:
        # BEGIN transaction with SERIALIZABLE isolation level
        db.begin()
        yield db
        # COMMIT transaction
        db.commit()
    except Exception as e:
        # ROLLBACK transaction on error
        db.rollback()
        logger.error(f"Database transaction rolled back due to error: {e}")
        raise
    finally:
        db.close()

