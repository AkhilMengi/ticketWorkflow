import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

SF_CLIENT_ID: str = os.getenv("SF_CLIENT_ID", "")
SF_CLIENT_SECRET: str = os.getenv("SF_CLIENT_SECRET", "")
SF_LOGIN_URL: str = os.getenv("SF_LOGIN_URL", "https://login.salesforce.com")

# Set to "true" to skip real SF API calls during local testing
MOCK_SALESFORCE: bool = os.getenv("MOCK_SALESFORCE", "true").lower() == "true"

# Set to "true" to skip real billing API calls
MOCK_BILLING: bool = os.getenv("MOCK_BILLING", "true").lower() == "true"

BILLING_API_URL: str = os.getenv("BILLING_API_URL", "http://localhost:9000")

SHEET_API_URL: str = os.getenv("SHEET_API_URL", "http://localhost:9001")

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./agent.db")
