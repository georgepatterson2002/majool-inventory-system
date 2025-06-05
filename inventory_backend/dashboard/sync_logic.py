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

        url = "https://api.veeqo.com/orders"
        headers = {
            "x-api-key": VEEQO_API_KEY,
            "accept": "application/json"
        }
        params = {
            "status": "shipped",
            "updated_at_min": (today - timedelta(days=7)).isoformat(),
            "page_size": 100
        }

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        raw_orders = response.json()

        filtered = [
            o for o in raw_orders
            if o.get("shipped_at") and
               datetime.fromisoformat(o["shipped_at"].replace("Z", "+00:00")) >= today
        ]
        return filtered

    orders = fetch_orders()
    updated = []

    with engine.begin() as conn:
        for order in orders:
            order_id = order.get("number")
            shipped_time_str = order.get("shipped_at")
            shipped_time = datetime.fromisoformat(shipped_time_str.replace("Z", "+00:00"))


            notes = order.get("employee_notes", [])
            serials = [n.get("text", "").strip() for n in notes if n.get("text")]

            total_quantity = sum(
                item.get("quantity", 0)
                for allocation in order.get("allocations", [])
                for item in allocation.get("line_items", [])
            )

            if len(serials) != total_quantity:
                inserted = set()
                for allocation in order.get("allocations", []):
                    for alloc_item in allocation.get("line_items", []):
                        sku = alloc_item.get("sellable", {}).get("sku_code")
                        if sku and (order_id, sku) not in inserted:
                            inserted.add((order_id, sku))
                            existing = conn.execute(text("""
                                SELECT resolved FROM manual_review
                                WHERE order_id = :order_id AND sku = :sku
                            """), {"order_id": order_id, "sku": sku}).fetchone()

                            if not existing:
                                conn.execute(text("""
                                    INSERT INTO manual_review (order_id, sku, created_at)
                                    VALUES (:order_id, :sku, :created_at)
                                """), {"order_id": order_id, "sku": sku, "created_at": shipped_time})
                            elif existing.resolved:
                                pass
                continue

            serial_pointer = 0
            for allocation in order.get("allocations", []):
                for alloc_item in allocation.get("line_items", []):
                    sku = alloc_item.get("sellable", {}).get("sku_code")
                    quantity = alloc_item.get("quantity", 0)

                    for _ in range(quantity):
                        if serial_pointer >= len(serials):
                            break

                        serial = serials[serial_pointer]
                        serial_pointer += 1

                        result = conn.execute(text("""
                            INSERT INTO inventory_log (sku, serial_number, order_id, event_time)
                            VALUES (:sku, :serial, :order_id, :event_time)
                            ON CONFLICT (serial_number) DO NOTHING
                            RETURNING serial_number
                        """), {
                            "sku": sku,
                            "serial": serial,
                            "order_id": order_id,
                            "event_time": datetime.now(pytz.timezone("America/Los_Angeles"))
                        })

                        if result.fetchone():
                            updated.append({"serial": serial, "order_id": order_id})
                            conn.execute(text("""
                                DELETE FROM inventory_units
                                WHERE serial_number = :serial
                            """), {"serial": serial})

    return updated
