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

        all_orders = []
        page = 1
        while True:
            params = {
                "status": "shipped",
                "updated_at_min": (today - timedelta(days=7)).isoformat(),
                "page_size": 100,
                "page": page
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            raw_orders = response.json()
            if not raw_orders:
                break

            filtered = [
                o for o in raw_orders
                if o.get("shipped_at") and
                datetime.fromisoformat(o["shipped_at"].replace("Z", "+00:00")) >= today
            ]
            all_orders.extend(filtered)
            page += 1

        return all_orders

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
                continue

            serial_pointer = 0
            for allocation in order.get("allocations", []):
                for alloc_item in allocation.get("line_items", []):
                    sku = alloc_item.get("sellable", {}).get("sku_code")
                    quantity = alloc_item.get("quantity", 0)

                    for _ in range(quantity):
                        if serial_pointer >= len(serials):
                            print(f"[WARNING] Serial list exhausted early for SKU: {sku} in Order: {order_id}")
                            continue

                        serial = serials[serial_pointer]
                        serial_pointer += 1

                        # Just insert new record, no need to check or delete existing ones
                        conn.execute(text("""
                            INSERT INTO inventory_log (sku, serial_number, order_id, event_time)
                            VALUES (:sku, :serial, :order_id, :event_time)
                            ON CONFLICT (serial_number, order_id) DO NOTHING
                        """), {
                            "sku": sku,
                            "serial": serial,
                            "order_id": order_id,
                            "event_time": shipped_time
                        })


                        updated.append({"serial": serial, "order_id": order_id})

                        conn.execute(text("""
                            UPDATE inventory_units
                            SET sold = TRUE
                            WHERE serial_number = :serial;
                        """), {"serial": serial})

            # HARD LIMIT: Only apply SSD logic for orders shipped on or after July 11, 2025
            ssd_cutoff = datetime(2025, 7, 11, 0, 0, 0, tzinfo=pytz.timezone("America/Los_Angeles"))

            # Skip SSD logic if it's a return-based order
            is_return_order = conn.execute(text("""
                SELECT 1
                FROM returns r
                JOIN inventory_units iu ON r.original_unit_id = iu.unit_id
                JOIN inventory_log il ON il.serial_number = iu.serial_number
                WHERE il.order_id = :order_id
                LIMIT 1
            """), {"order_id": order_id}).fetchone()


            if shipped_time >= ssd_cutoff:
                total_ssds_needed = sum(
                    item.get("quantity", 0)
                    for allocation in order.get("allocations", [])
                    for item in allocation.get("line_items", [])
                    if "+1tb" in (item.get("sellable", {}).get("sku_code") or "").lower()
                )

                if total_ssds_needed > 0:
                    existing_ssd_count = conn.execute(text("""
                        SELECT COUNT(*) FROM inventory_log il
                        JOIN inventory_units iu ON il.serial_number = iu.serial_number
                        JOIN products p ON iu.product_id = p.product_id
                        WHERE il.order_id = :order_id AND p.ssd_id = 2
                    """), {"order_id": order_id}).scalar()

                    remaining = total_ssds_needed - existing_ssd_count
                    if remaining > 0:
                        ssd_rows = conn.execute(text("""
                            SELECT iu.serial_number
                            FROM inventory_units iu
                            JOIN products p ON iu.product_id = p.product_id
                            WHERE iu.sold = FALSE AND p.ssd_id = 2
                            ORDER BY iu.serial_assigned_at ASC
                            LIMIT :qty
                        """), {"qty": remaining}).fetchall()

                        if len(ssd_rows) < remaining:
                            print(f"[WARNING] Only found {len(ssd_rows)} available SSDs for Order {order_id}, needed {remaining}")

                        for i in range(min(remaining, len(ssd_rows))):
                            ssd_serial = ssd_rows[i].serial_number

                            conn.execute(text("""
                                INSERT INTO inventory_log (sku, serial_number, order_id, event_time)
                                VALUES ('SSD-1TB', :serial, :order_id, :event_time)
                            """), {
                                "serial": ssd_serial,
                                "order_id": order_id,
                                "event_time": shipped_time
                            })

                            conn.execute(text("""
                                UPDATE inventory_units SET sold = TRUE WHERE serial_number = :serial
                            """), {"serial": ssd_serial})

                            print(f"[SSD] Marked 1TB SSD {ssd_serial} as sold for Order {order_id}")
            elif is_return_order:
                 print(f"[SSD] Skipping SSD logic for Order {order_id} — contains return serials")


            if serial_pointer < len(serials):
                unassigned = serials[serial_pointer:]
                print(f"[INFO] Unused serials for order {order_id}: {unassigned}")

    return updated
