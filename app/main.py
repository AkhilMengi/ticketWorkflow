from fastapi import FastAPI
from app.api.routes import router
from app.integrations.db import init_db
from app.workers.worker import start_worker

app = FastAPI(title="Intelligent Salesforce Agent")

@app.on_event("startup")
def startup():
    init_db()
    start_worker()

app.include_router(router, prefix="/api")