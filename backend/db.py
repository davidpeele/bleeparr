import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "bleeparr.db"

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bleeparr_items (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL CHECK (type IN ('show', 'movie')),
                filtered BOOLEAN NOT NULL DEFAULT 0
            )
        """)
