import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Salesforce Configuration
    SF_CLIENT_ID = os.getenv("SF_CLIENT_ID")
    SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET")
    SF_USERNAME = os.getenv("SF_USERNAME")
    SF_PASSWORD = os.getenv("SF_PASSWORD")
    SF_SECURITY_TOKEN = os.getenv("SF_SECURITY_TOKEN")
    SF_LOGIN_URL = os.getenv("SF_LOGIN_URL", "https://login.salesforce.com")
    SF_API_VERSION = os.getenv("SF_API_VERSION", "v61.0")  # ✅ CONFIGURABLE - SECURITY FIX

    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agent.db")
    
    # Security Configuration ✅
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-key-in-production")
    ALGORITHM = "HS256"
    TOKEN_EXPIRATION_HOURS = int(os.getenv("TOKEN_EXPIRATION_HOURS", "24"))

settings = Settings()
