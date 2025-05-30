import os
import csv
from datetime import datetime, timedelta
from sqlalchemy import text
from inventory_backend.database import engine
import pytz

def run_backup():
    print("Starting backup...")

    now = datetime.now(pytz.timezone("America/Los_Angeles"))
    date_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")
    is_month_end = now.month != (now + timedelta(days=1)).month

    base_path = os.path.dirname(__file__)
    backup_dir = os.path.join(base_path, "..", "backups", "monthly", month_str) if is_month_end \
        else os.path.join(base_path, "..", "backups", date_str)
    backup_dir = os.path.abspath(backup_dir)

    os.makedirs(backup_dir, exist_ok=True)

    try:
        with engine.begin() as conn:
            def write_csv(filename, result):
                rows = result.fetchall()
                cols = result.keys()
                with open(f"{backup_dir}/{filename}", "w", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(cols)
                    writer.writerows(rows)

            # Inventory Units
            result = conn.execute(text("SELECT * FROM inventory_units"))
            write_csv("inventory_units.csv", result)

            # Inventory Log
            if is_month_end:
                first_day = now.replace(day=1).strftime("%Y-%m-%d")
                last_day = now.strftime("%Y-%m-%d")
                result = conn.execute(text("""
                    SELECT * FROM inventory_log
                    WHERE event_time BETWEEN :start AND :end
                """), {"start": first_day, "end": last_day})
            else:
                result = conn.execute(text("SELECT * FROM inventory_log"))
            write_csv("inventory_log.csv", result)

            # Manual Review
            result = conn.execute(text("SELECT * FROM manual_review"))
            write_csv("manual_review.csv", result)

        print(f"Backup complete: {backup_dir}")
        print(f"Backup complete: {os.path.abspath(backup_dir)}")
    except Exception as e:
        print("Backup failed:", e)
