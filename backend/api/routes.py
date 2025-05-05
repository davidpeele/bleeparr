from fastapi import APIRouter, HTTPException
from api.sonarr import fetch_sonarr_series
from api.bleeparr_core import clean_file
from db.crud import get_monitored_shows

router = APIRouter(prefix="/api")

@router.get("/shows")
def get_shows():
    try:
        return fetch_sonarr_series()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitored")
def get_monitored():
    return get_monitored_shows()

@router.post("/clean")
def clean_endpoint(file_path: str, dry_run: bool = False):
    return clean_file(file_path, dry_run=dry_run)
