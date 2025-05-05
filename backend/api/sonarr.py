import os
import requests

SONARR_URL = os.getenv("SONARR_URL", "http://localhost:8989")
SONARR_API_KEY = os.getenv("SONARR_API_KEY", "your_api_key")

def fetch_sonarr_series():
    url = f"{SONARR_URL}/api/v3/series"
    headers = {"X-Api-Key": SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()
