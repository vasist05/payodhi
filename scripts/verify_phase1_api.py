"""
scripts/verify_phase1_api.py

Verify Phase 1 backend API routes and schemas.
"""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))
sys.path.insert(0, str(ROOT_DIR))

def main():
    print("Loading FastAPI app...")
    try:
        from app.main import app
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

    openapi = app.openapi()
    paths = openapi.get("paths", {})
    print("\nResolved OpenAPI Endpoints:")
    for path, methods in paths.items():
        print(f"  {','.join(methods.keys()).upper():<10} {path}")

    assert "/api/v1/detection/detect" in paths, "Missing /api/v1/detection/detect route!"
    assert "/api/v1/detection/detect-and-filter" in paths, "Missing /api/v1/detection/detect-and-filter route!"
    assert "/api/v1/spills/filter" in paths, "Missing /api/v1/spills/filter route!"

    print("\nPhase 1 API Verification: ALL ROUTES VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
