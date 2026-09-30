from fastapi import APIRouter, HTTPException, Query
import os
import requests
from backend.db import get_db

router = APIRouter()

# Fetch shows from Sonarr
@router.get("/api/shows")
def get_shows():
    url = os.getenv("SONARR_URL")
    api_key = os.getenv("SONARR_API_KEY")

    if not url or not api_key:
        raise HTTPException(status_code=500, detail="Sonarr URL or API key not set")

    try:
        response = requests.get(f"{url}/api/v3/series", headers={"X-Api-Key": api_key})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=str(e))

# Generalized filtered flag routes for shows or movies
@router.get("/api/filtered/{item_type}")
def get_filtered_items(item_type: str):
    if item_type not in ("show", "movie"):
        raise HTTPException(status_code=400, detail="Invalid item type")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, filtered FROM bleeparr_items WHERE type = ?", (item_type,))
    return [{"id": row[0], "filtered": bool(row[1])} for row in cursor.fetchall()]

@router.put("/api/filtered/{item_type}/{item_id}")
def update_filtered_item(item_type: str, item_id: int, filtered: bool = Query(...)):
    if item_type not in ("show", "movie"):
        raise HTTPException(status_code=400, detail="Invalid item type")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM bleeparr_items WHERE id = ? AND type = ?", (item_id, item_type))
    exists = cursor.fetchone()
    if exists:
        cursor.execute("UPDATE bleeparr_items SET filtered = ? WHERE id = ? AND type = ?", (int(filtered), item_id, item_type))
    else:
        cursor.execute("INSERT INTO bleeparr_items (id, type, filtered) VALUES (?, ?, ?)", (item_id, item_type, int(filtered)))
    conn.commit()
    return {"id": item_id, "type": item_type, "filtered": filtered}

def update_filtered(series_id: int, filtered: bool = Query(...)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bleeparr_items (id, type, filtered)
        VALUES (?, 'show', ?)
        ON CONFLICT(id) DO UPDATE SET filtered = excluded.filtered
    """, (series_id, int(filtered)))
    conn.commit()
    return {"series_id": series_id, "filtered": filtered}
