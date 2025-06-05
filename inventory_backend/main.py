from fastapi import FastAPI
from inventory_backend.scanner.routes import router as scanner_router
from inventory_backend.dashboard.routes import router as dashboard_router
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from inventory_backend.dashboard.routes import sync_veeqo_orders
from inventory_backend.dashboard.sync_logic import sync_veeqo_orders_job
from inventory_backend.dashboard.backup import run_backup
import pytz

import threading
import time

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from fastapi.middleware.cors import CORSMiddleware

run_backup()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the scanner and dashboard routers
app.include_router(scanner_router, prefix="/scanner")
app.include_router(dashboard_router, prefix="/dashboard")


def start_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone("America/Los_Angeles"))

    # Veeqo sync every 1 min
    scheduler.add_job(sync_veeqo_orders_job, IntervalTrigger(minutes=1))

    # Daily backup at 4:00 PM
    scheduler.add_job(run_backup, CronTrigger(hour=16, minute=0))

    scheduler.start()
    print("Scheduler started: Sync every 1 min, Backup at 4 PM")
    print("Scheduler started: Sync every 1 min, Backup at 4 PM")

start_scheduler()

# === Serve React Frontend ===
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inventory_dashboard", "frontend", "dist"))
app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

# Optional: default to index.html if no route matches (React handles routing)
@app.get("/{full_path:path}")
async def serve_react_app():
    return FileResponse(os.path.join(frontend_dist, "index.html"))

LOG_DIR = r"C:\Logs"
MAX_LOG_SIZE_MB = 100
MAX_LOG_SIZE_BYTES = MAX_LOG_SIZE_MB * 1024 * 1024


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("inventory_backend.main:app", host="0.0.0.0", port=8000, reload=False)