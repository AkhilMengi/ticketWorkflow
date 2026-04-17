import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    SF_CLIENT_ID = os.getenv("SF_CLIENT_ID")
    SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET")
    SF_USERNAME = os.getenv("SF_USERNAME")
    SF_PASSWORD = os.getenv("SF_PASSWORD")
    SF_SECURITY_TOKEN = os.getenv("SF_SECURITY_TOKEN")
    SF_LOGIN_URL = os.getenv("SF_LOGIN_URL", "https://login.salesforce.com")

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agent.db")

settings = Settings()