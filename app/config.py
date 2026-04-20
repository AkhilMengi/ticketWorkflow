import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class Settings:
    # API Settings
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Logging Settings
    LOG_LEVEL = LOG_LEVEL
    
    # AI/LLM Settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Salesforce Settings
    SF_CLIENT_ID = os.getenv("SF_CLIENT_ID")
    SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET")
    SF_USERNAME = os.getenv("SF_USERNAME")
    SF_PASSWORD = os.getenv("SF_PASSWORD")
    SF_SECURITY_TOKEN = os.getenv("SF_SECURITY_TOKEN")
    SF_LOGIN_URL = os.getenv("SF_LOGIN_URL", "https://login.salesforce.com")

    # Database Settings
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agent.db")
    DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "5"))
    DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))
    DATABASE_POOL_TIMEOUT = int(os.getenv("DATABASE_POOL_TIMEOUT", "30"))
    DATABASE_POOL_RECYCLE = int(os.getenv("DATABASE_POOL_RECYCLE", "3600"))
    # Transaction isolation level: SERIALIZABLE, REPEATABLE_READ, READ_COMMITTED, READ_UNCOMMITTED
    DATABASE_ISOLATION_LEVEL = os.getenv("DATABASE_ISOLATION_LEVEL", "SERIALIZABLE")

    # Worker Settings
    WORKER_RETRY_ATTEMPTS = int(os.getenv("WORKER_RETRY_ATTEMPTS", "3"))
    WORKER_RETRY_DELAY = int(os.getenv("WORKER_RETRY_DELAY", "1"))  # seconds
    
    # API Settings
    MAX_REQUEST_SIZE = int(os.getenv("MAX_REQUEST_SIZE", "1048576"))  # 1MB

settings = Settings()
