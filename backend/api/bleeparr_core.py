import subprocess
import logging

def clean_file(file_path: str, dry_run: bool = False):
    cmd = ["python3", "bleeparr-1.1.py", "--input", file_path]
    if dry_run:
        cmd.append("--dry-run")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {"status": "success", "output": result.stdout}
    except subprocess.CalledProcessError as e:
        logging.error(e.stderr)
        return {"status": "error", "error": e.stderr}
