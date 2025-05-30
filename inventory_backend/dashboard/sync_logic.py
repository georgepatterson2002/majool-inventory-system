from datetime import datetime, timedelta
from sqlalchemy import text
import pytz
import requests
import os
from inventory_backend.database import engine

VEEQO_API_KEY = os.getenv("VEEQO_API_KEY")

def sync_veeqo_orders_job():
    def fetch_orders():
        now_local = datetime.now(pytz.timezone("America/Los_Angeles"))
        today = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)

        url = "https://api.veeqo.com/orders"
        headers = {
            "x-api-key": VEEQO_API_KEY,
            "accept": "application/json"
        }
        params = {
            "status": "shipped",
            "created_at_min": yesterday.isoformat(),
            "page_size": 100
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        return [
            o for o in response.json()
            if o.get("shipped_at") and
               datetime.fromisoformat(o["shipped_at"].replace("Z", "+00:00")) >= today
        ]

    orders = fetch_orders()
    updated = []

    with engine.begin() as conn:
        for order in orders:
            shipped_time = order.get("shipped_at")
            notes = order.get("employee_notes", [])
            serials = [n.get("text", "").strip() for n in notes if n.get("text")]
            inserted = set()

            for allocation in order.get("allocations", []):
                for alloc_item in allocation.get("line_items", []):
                    sku = alloc_item.get("sellable", {}).get("sku_code")
                    quantity = alloc_item.get("quantity", 0)

                    if not serials:
                        if sku and (order["number"], sku) not in inserted:
                            inserted.add((order["number"], sku))
                            conn.execute(text("""
                                INSERT INTO manual_review (order_id, sku, created_at)
                                VALUES (:order_id, :sku, :created_at)
                                ON CONFLICT DO NOTHING
                            """), {
                                "order_id": order["number"],
                                "sku": sku,
                                "created_at": shipped_time
                            })
                        continue

                    for serial in serials[:quantity]:
                        result = conn.execute(text("""
                            INSERT INTO inventory_log (sku, serial_number, order_id, event_time)
                            VALUES (:sku, :serial, :order_id, :event_time)
                            ON CONFLICT (serial_number) DO NOTHING
                            RETURNING serial_number
                        """), {
                            "sku": sku,
                            "serial": serial,
                            "order_id": order["number"],
                            "event_time": shipped_time
                        })

                        if result.fetchone():
                            updated.append({"serial": serial, "order_id": order["number"]})
                            conn.execute(text("""
                                DELETE FROM inventory_units
                                WHERE serial_number = :serial
                            """), {"serial": serial})

    print(f"Veeqo Sync Complete: {len(updated)} serials updated")
    return updated
