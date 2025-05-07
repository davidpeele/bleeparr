import sqlite3
from pathlib import Path
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('bleeparr.db')

# Define database path
DB_PATH = Path(__file__).parent / "bleeparr.db"

def get_db():
    """Get a database connection"""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initialize the database schema"""
    logger.info(f"Initializing database at {DB_PATH}")
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create table for filtered items (shows/movies)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bleeparr_items (
                id INTEGER PRIMARY KEY,
                type TEXT NOT NULL CHECK (type IN ('show', 'movie')),
                filtered BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create table for processing history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                item_type TEXT NOT NULL CHECK (type IN ('show', 'movie')),
                file_path TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                parent_id INTEGER,
                swears_found INTEGER DEFAULT 0,
                success BOOLEAN NOT NULL DEFAULT 0,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP
            )
        """)
        
        # Create table for application settings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert default settings if not present
        default_settings = [
            ('sonarr_url', os.getenv('SONARR_URL', '')),
            ('sonarr_api_key', os.getenv('SONARR_API_KEY', '')),
            ('radarr_url', os.getenv('RADARR_URL', '')),
            ('radarr_api_key', os.getenv('RADARR_API_KEY', '')),
            ('swears_file', os.getenv('SWEARS_FILE', 'swears.txt')),
            ('output_prefix', 'clean_'),
            ('output_directory', ''),
            ('enable_auto_processing', '1'),
            ('poll_interval_seconds', '300'),
            ('boost_db', '6'),
            ('pre_buffer', '100'),
            ('post_buffer', '100'),
            ('bleeptool', 'S-M-FSM')
        ]
        
        for key, value in default_settings:
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bleeparr_items_type ON bleeparr_items (type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_history_item ON processing_history (item_id, item_type)")
        
        conn.commit()
        logger.info("Database initialization complete")

def get_setting(key, default=None):
    """Get a setting value from the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return default

def set_setting(key, value):
    """Set a setting value in the database"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP",
            (key, value, value)
        )
        conn.commit()
    return True

def get_all_settings():
    """Get all settings as a dictionary"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        return {row[0]: row[1] for row in cursor.fetchall()}

def save_processing_history(item):
    """Save an item to the processing history"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO processing_history 
            (item_id, item_type, file_path, title, detail, parent_id, swears_found, success, error, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                item.get('id'),
                item.get('type'),
                item.get('file_path'),
                item.get('title'),
                item.get('detail', ''),
                item.get('parent_id'),
                item.get('result', {}).get('swears_found', 0) if item.get('success', False) else 0,
                1 if item.get('success', False) else 0,
                item.get('result', {}).get('error', None) if not item.get('success', False) else None
            )
        )
        conn.commit()
    return True

def get_processing_history(limit=100, offset=0, item_type=None):
    """Get processing history items"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM processing_history"
        params = []
        
        if item_type:
            query += " WHERE item_type = ?"
            params.append(item_type)
        
        query += " ORDER BY processed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
