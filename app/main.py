from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.api.routes import router
from app.integrations.db import init_db
from app.workers.worker import start_worker
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Intelligent Salesforce Agent")

# Add middleware for request validation and error handling
@app.middleware("http")
async def validate_request_size(request: Request, call_next):
    """Middleware to validate request size"""
    # Maximum request size: 1MB
    MAX_REQUEST_SIZE = 1024 * 1024
    
    # Check Content-Length header
    content_length = request.headers.get('content-length')
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={
                "detail": f"Request body too large. Maximum size is {MAX_REQUEST_SIZE / 1024 / 1024}MB",
                "error_code": "REQUEST_TOO_LARGE"
            }
        )
    
    response = await call_next(request)
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Enhanced validation error handler with detailed error information"""
    errors = []
    for error in exc.errors():
        error_detail = {
            "field": ".".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        }
        errors.append(error_detail)
    
    logger.warning(f"Validation error for {request.url.path}: {errors}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation failed",
            "errors": errors,
            "error_code": "VALIDATION_ERROR"
        }
    )

@app.on_event("startup")
def startup():
    init_db()
    start_worker()

app.include_router(router, prefix="/api")
