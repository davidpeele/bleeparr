from fastapi import APIRouter, HTTPException, BackgroundTasks
import os
import subprocess
import logging
import sys
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
import sqlite3
import json
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger('bleeparr.admin')

# Models
class AdminSettings(BaseModel):
    port: int = 5050
    logLevel: str = "INFO"
    maxHistoryItems: int = 100
    maxQueueItems: int = 50

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str

# Helper functions
def get_db_connection():
    db_path = os.path.join(os.path.dirname(__file__), "../bleeparr.db")
    return sqlite3.connect(db_path)

def read_logs(max_entries: int = 100):
    logs = []
    try:
        # Read logs from a log file or database
        # This is a placeholder - adjust to your actual logging setup
        log_path = os.path.join(os.path.dirname(__file__), "../../logs/bleeparr.log")
        
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                log_lines = f.readlines()[-max_entries:]
                
                for line in log_lines:
                    try:
                        # Parse log line - format may vary based on your logging config
                        parts = line.split(' - ', 3)
                        if len(parts) >= 3:
                            timestamp = parts[0]
                            level = parts[1]
                            message = ' - '.join(parts[2:])
                            logs.append(LogEntry(
                                timestamp=timestamp,
                                level=level,
                                message=message
                            ))
                    except Exception as e:
                        logger.error(f"Error parsing log line: {e}")
                        continue
        else:
            # If log file doesn't exist, create some sample entries
            logs = [
                LogEntry(
                    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    level="INFO",
                    message="No log file found. This is a simulated log entry."
                )
            ]
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        logs = [
            LogEntry(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                level="ERROR",
                message=f"Failed to read logs: {str(e)}"
            )
        ]
    
    return logs

def get_admin_settings():
    # This would ideally read from a config file or database
    # For now, we'll return default values
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Try to get settings from database
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('port', 'logLevel', 'maxHistoryItems', 'maxQueueItems')")
        results = cursor.fetchall()
        
        settings = AdminSettings()
        
        for key, value in results:
            if key == 'port':
                settings.port = int(value)
            elif key == 'logLevel':
                settings.logLevel = value
            elif key == 'maxHistoryItems':
                settings.maxHistoryItems = int(value)
            elif key == 'maxQueueItems':
                settings.maxQueueItems = int(value)
        
        conn.close()
        return settings
    except Exception as e:
        logger.error(f"Error getting admin settings: {e}")
        return AdminSettings()

def save_admin_settings(settings: AdminSettings):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update or insert settings
        for key, value in settings.dict().items():
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value))
            )
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving admin settings: {e}")
        return False

# Routes
@router.get("/api/admin/settings")
def admin_settings():
    """Get admin settings"""
    return get_admin_settings()

@router.post("/api/admin/settings")
def update_admin_settings(settings: AdminSettings):
    """Update admin settings"""
    if save_admin_settings(settings):
        return {"success": True, "message": "Settings saved successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save settings")

@router.get("/api/admin/logs")
def get_logs(max_entries: int = 100):
    """Get application logs"""
    logs = read_logs(max_entries)
    return {"logs": logs}

@router.post("/api/admin/reset-queue")
def reset_queue():
    """Reset the processing queue"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processing_queue")
        conn.commit()
        conn.close()
        logger.info("Processing queue was reset by admin")
        return {"success": True, "message": "Processing queue reset successfully"}
    except Exception as e:
        logger.error(f"Failed to reset processing queue: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset queue: {str(e)}")

@router.post("/api/admin/reset-history")
def reset_history():
    """Reset the processing history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processing_history")
        conn.commit()
        conn.close()
        logger.info("Processing history was reset by admin")
        return {"success": True, "message": "Processing history reset successfully"}
    except Exception as e:
        logger.error(f"Failed to reset processing history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset history: {str(e)}")

@router.post("/api/admin/reboot")
def reboot_application(background_tasks: BackgroundTasks):
    """Reboot the application"""
    def restart_app():
        # Wait a few seconds before restarting
        time.sleep(3)
        # If using Docker, you might need a different approach
        # This is a simulated reboot for development
        logger.info("Application reboot initiated")
        try:
            # For Docker environment, touch a restart trigger file
            with open("/app/restart_trigger", "w") as f:
                f.write(str(datetime.now()))
        except:
            # Fallback approach
            os.execv(sys.executable, [sys.executable] + sys.argv)
    
    # Add the restart task to run in the background
    background_tasks.add_task(restart_app)
    
    return {"success": True, "message": "Application is rebooting..."}

@router.get("/api/admin/system-info")
def system_info():
    """Get system information"""
    try:
        info = {
            "timestamp": datetime.now().isoformat(),
            "python_version": sys.version,
            "platform": sys.platform,
            "cpu_usage": None,
            "memory_usage": None,
            "disk_usage": None,
        }
        
        # Try to get more detailed info if psutil is available
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            info["cpu_usage"] = cpu
            info["memory_usage"] = {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent
            }
            info["disk_usage"] = {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            }
        except ImportError:
            # psutil not available
            pass
        
        return info
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting system info: {str(e)}")
