import json
import uuid
from app.integrations.db import SessionLocal, MemoryRecord

def save_long_term_memory(user_id: str, memory_type: str, payload: dict):
    db = SessionLocal()
    try:
        record = MemoryRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            memory_type=memory_type,
            payload=json.dumps(payload)
        )
        db.add(record)
        db.commit()
    finally:
        db.close()

def get_long_term_memory(user_id: str):
    db = SessionLocal()
    try:
        records = db.query(MemoryRecord).filter(MemoryRecord.user_id == user_id).all()
        return [
            {
                "id": r.id,
                "memory_type": r.memory_type,
                "payload": json.loads(r.payload) if r.payload else {}
            }
            for r in records
        ]
    finally:
        db.close()