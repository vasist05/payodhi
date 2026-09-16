"""
run_backend.py
==============
Launcher script to run the NTRO Oil Spill Forensics Attribution API server.
Usage:
    python run_backend.py
"""

import sys
import uvicorn

if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    print("=" * 70)
    print("  🚢 NTRO MARITIME SURVEILLANCE & ATTRIBUTION API SERVER")
    print("  Connecting Phases 1 - 6 to React Dashboard")
    print("  URL: http://127.0.0.1:8000")
    print("  Docs: http://127.0.0.1:8000/docs")
    print("=" * 70)

    uvicorn.run("backend.api.main:app", host="127.0.0.1", port=8000, reload=True)
