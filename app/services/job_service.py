import json
import uuid
from datetime import datetime
from app.integrations.db import SessionLocal, JobRecord, EventRecord

def create_job(payload: dict) -> str:
    db = SessionLocal()
    try:
        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            status="queued",
            input_payload=json.dumps(payload),
            updated_at=datetime.utcnow()
        )
        db.add(record)
        db.commit()
        return job_id
    finally:
        db.close()

def update_job(job_id: str, status: str, result: dict | None = None):
    db = SessionLocal()
    try:
        job = db.query(JobRecord).filter(JobRecord.job_id == job_id).first()
        if job:
            job.status = status
            job.updated_at = datetime.utcnow()
            if result is not None:
                job.result_payload = json.dumps(result)
            db.commit()
    finally:
        db.close()

def get_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(JobRecord).filter(JobRecord.job_id == job_id).first()
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "status": job.status,
            "result": json.loads(job.result_payload) if job.result_payload else None
        }
    finally:
        db.close()

def add_event(job_id: str, event_type: str, payload: dict):
    db = SessionLocal()
    try:
        db.add(EventRecord(
            id=str(uuid.uuid4()),
            job_id=job_id,
            event_type=event_type,
            payload=json.dumps(payload)
        ))
        db.commit()
    finally:
        db.close()

def get_events(job_id: str):
    db = SessionLocal()
    try:
        events = db.query(EventRecord).filter(EventRecord.job_id == job_id).order_by(EventRecord.created_at.asc()).all()
        return [
            {
                "type": e.event_type,
                "payload": json.loads(e.payload) if e.payload else {},
                "created_at": e.created_at.isoformat()
            }
            for e in events
        ]
    finally:
        db.close()