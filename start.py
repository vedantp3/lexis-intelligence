"""
Production entry point — reads PORT from environment variable (set by Render/Railway/etc.)
Run with: python start.py
"""
import os
import sys
import traceback

print("=== START.PY BOOT ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"PORT env: {os.environ.get('PORT', 'NOT SET')}", flush=True)

try:
    print("Step 1: Importing uvicorn...", flush=True)
    import uvicorn
    print("Step 1: OK", flush=True)

    print("Step 2: Importing backend.main...", flush=True)
    from backend.main import app          # <-- catches import crashes with full traceback
    print("Step 2: OK — FastAPI app loaded", flush=True)

    port = int(os.environ.get("PORT", 8000))
    print(f"Step 3: Starting server on 0.0.0.0:{port} ...", flush=True)

    uvicorn.run(
        app,                              # pass object, not string — no second import needed
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
    )

except Exception as exc:
    print("\n=== FATAL CRASH ===", flush=True)
    traceback.print_exc()
    sys.exit(1)

