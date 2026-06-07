import os
import sys
import subprocess
from database import init_db
from seed_exercises import seed_database

# Fix encoding issues if any
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

print("=== Starting Coding Trainer Backend ===")

# 1. Initialize and migrate the SQLite database structure
print("[1/3] Initializing SQLite database...")
init_db()

# 2. Seed exercises if database is empty
print("[2/3] Checking and seeding exercises...")
seed_database()

# 3. Read PORT and start Gunicorn
port = os.environ.get("PORT", "5000")
print(f"[3/3] Starting Gunicorn server on port {port}...")

# Run Gunicorn
cmd = ["gunicorn", "app:app", "--bind", f"0.0.0.0:{port}", "--workers", "2", "--timeout", "120"]
subprocess.run(cmd)
