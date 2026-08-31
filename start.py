"""
Production entry point — reads PORT from environment variable (set by Render/Railway/etc.)
Run with: python start.py
"""
import os
import sys
import traceback

print(f"=== START.PY BOOT ===", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"PORT env: {os.environ.get('PORT', 'NOT SET')}", flush=True)
print(f"sys.path: {sys.path[:3]}", flush=True)

try:
    import uvicorn
    print("uvicorn: OK", flush=True)

    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    print(f"Binding to {host}:{port} ...", flush=True)

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
except Exception as exc:
    print(f"\n=== FATAL CRASH ===", flush=True)
    traceback.print_exc()
    sys.exit(1)

