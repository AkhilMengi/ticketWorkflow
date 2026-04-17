import requests
from dotenv import load_dotenv
import os

load_dotenv()

SF_LOGIN_URL = os.getenv("SF_LOGIN_URL")
SF_CLIENT_ID = os.getenv("SF_CLIENT_ID")
SF_CLIENT_SECRET = os.getenv("SF_CLIENT_SECRET")

print(f"SF_LOGIN_URL: {SF_LOGIN_URL}")
print(f"SF_CLIENT_ID: {SF_CLIENT_ID[:20] if SF_CLIENT_ID else 'Not set'}...")
print("\n--- Attempting Client Credentials Grant Flow ---\n")

url = f"{SF_LOGIN_URL}/services/oauth2/token"

payload = {
    "grant_type": "client_credentials",
    "client_id": SF_CLIENT_ID,
    "client_secret": SF_CLIENT_SECRET
}

print(f"URL: {url}")
print(f"Payload keys: {payload.keys()}")

try:
    response = requests.post(url, data=payload, timeout=20)
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body:\n{response.text}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"\nSuccess! Access Token: {data.get('access_token')[:20]}...")
        print(f"Instance URL: {data.get('instance_url')}")
    else:
        print(f"\nError Response: {response.json()}")
        
except Exception as e:
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()
