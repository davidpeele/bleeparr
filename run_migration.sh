#!/bin/bash
# Run the database migration script in the Docker container

echo "Creating migration script in container..."
docker exec -it bleeparr bash -c "cat > /tmp/migrate_db.py" << 'EOL'
import os
import shutil
import sqlite3
from pathlib import Path

# Define paths
old_db_path = "/app/backend/bleeparr.db"
new_db_path = "/app/data/bleeparr.db"
new_dir = "/app/data"

print(f"Checking for old database at {old_db_path}")
if os.path.exists(old_db_path):
    print(f"Old database found at {old_db_path}")
    
    # Create data directory if it doesn't exist
    if not os.path.exists(new_dir):
        print(f"Creating data directory at {new_dir}")
        os.makedirs(new_dir, exist_ok=True)
    
    # Check if new database already exists
    if not os.path.exists(new_db_path):
        print(f"Copying database from {old_db_path} to {new_db_path}")
        shutil.copy2(old_db_path, new_db_path)
        print("Database migration complete")
    else:
        print(f"New database already exists at {new_db_path}, skipping migration")
else:
    print(f"Old database not found at {old_db_path}, no migration needed")
EOL

echo "Running migration script..."
docker exec -it bleeparr python3 /tmp/migrate_db.py
