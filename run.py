"""Entry point for the SDE Prep platform."""
import sys
import io

# Fix Windows console encoding for UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent / ".env")

from database import init_db
from seed_exercises import seed_database
from app import app
from config import PORT, DEBUG


def main():
    print("=" * 60)
    print("  🎯 SDE PREP — Senior Data Engineer Interview Platform")
    print("=" * 60)
    print()

    print("[*] Initializing database...")
    init_db()

    print("[*] Checking exercise library...")
    seed_database()

    print()
    print(f"[>] Starting server at http://localhost:{PORT}")
    print(f"    Open this URL in your browser to start training!")
    print()

    app.run(debug=DEBUG, port=PORT, host='0.0.0.0')


if __name__ == '__main__':
    main()
