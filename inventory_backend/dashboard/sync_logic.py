from datetime import datetime, timedelta
from sqlalchemy import text
import pytz
import requests
import os
from inventory_backend.database import engine

VEEQO_API_KEY = os.getenv("VEEQO_API_KEY")

def get_available_products_by_ssd(conn, ssd_id):
    result = conn.execute(text("""
        WITH unsold AS (
            SELECT p.product_id, COUNT(*) AS unsold_qty
            FROM inventory_units iu
            JOIN products p ON iu.product_id = p.product_id
            WHERE iu.sold = FALSE AND iu.serial_number != 'NOSER' AND p.ssd_id = :ssd_id
            GROUP BY p.product_id
        ),
        soft_alloc AS (
            SELECT product_id, SUM(quantity) AS soft_qty
            FROM untracked_serial_sales
            GROUP BY product_id
        )
        SELECT u.product_id, COALESCE(u.unsold_qty, 0) - COALESCE(sa.soft_qty, 0) AS available
        FROM unsold u
        LEFT JOIN soft_alloc sa ON u.product_id = sa.product_id
        WHERE (COALESCE(u.unsold_qty, 0) - COALESCE(sa.soft_qty, 0)) > 0
        ORDER BY available DESC
    """), {"ssd_id": ssd_id})
    return [dict(row) for row in result.fetchall()]


def sync_veeqo_orders_job():
    def fetch_orders():
        la_tz = pytz.timezone("America/Los_Angeles")
        now_local = datetime.now(la_tz)
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

            # Assuming raw_orders is a list of orders; adjust if API differs
            if not raw_orders:
                break

            # Filter orders shipped today or later (convert shipped_at to LA tz)
            filtered = []
            for o in raw_orders:
                shipped_at_str = o.get("shipped_at")
                if not shipped_at_str:
                    continue
                shipped_utc = datetime.fromisoformat(shipped_at_str.replace("Z", "+00:00"))
                shipped_la = shipped_utc.astimezone(la_tz)
                if shipped_la >= today:
                    filtered.append(o)

            all_orders.extend(filtered)
            page += 1

        return all_orders

    orders = fetch_orders()
    updated = []

    la_tz = pytz.timezone("America/Los_Angeles")
    ssd_cutoff = la_tz.localize(datetime(2025, 7, 11, 0, 0, 0))

    with engine.begin() as conn:
        for order in orders:
            order_id = order.get("number")

            # Add this check to skip already processed orders:
            existing_order = conn.execute(text("""
                SELECT 1 FROM inventory_log WHERE order_id = :order_id LIMIT 1
            """), {"order_id": order_id}).fetchone()
            if existing_order:
                print(f"[INFO] Order {order_id} already processed — skipping")
                continue
                
            shipped_time_str = order.get("shipped_at")
            shipped_utc = datetime.fromisoformat(shipped_time_str.replace("Z", "+00:00"))
            shipped_time = shipped_utc.astimezone(la_tz)

            notes = order.get("employee_notes", [])
            serials = [n.get("text", "").strip() for n in notes if n.get("text")]

            # --- 1. Calculate expected total serials accounting for enhanced SKUs ---
            expected_serials_total = 0
            sku_quantities = []  # For manual review insertion per SKU if needed
            for allocation in order.get("allocations", []):
                for item in allocation.get("line_items", []):
                    sku = item.get("sellable", {}).get("sku_code", "").lower()
                    qty = item.get("quantity", 0)
                    multiplier = 2 if any(k in sku for k in ["+512gb", "--512gb"]) else 1
                    expected = qty * multiplier
                    expected_serials_total += expected
                    sku_quantities.append((sku, expected))

            # --- 2. Check total serial count matches expected ---
            if len(serials) != expected_serials_total:
                # Special 512GB fallback: scanned qty == half of expected
                is_all_512 = all(any(k in sku for k in ["+512gb", "--512gb"]) for sku, _ in sku_quantities)
                total_qty = sum(qty for _, qty in sku_quantities)

                if is_all_512 and len(serials) == total_qty:
                    print(f"[INFO] Fallback: {len(serials)} serials for 512GB order with qty {total_qty} (expected {2 * total_qty})")

                    inserted_count = 0
                    for _ in range(total_qty):
                        row = conn.execute(text("""
                            SELECT iu.product_id
                            FROM inventory_units iu
                            JOIN products p ON iu.product_id = p.product_id
                            WHERE iu.sold = FALSE
                              AND iu.is_damaged = FALSE
                              AND iu.serial_number != 'NOSER'
                              AND p.ssd_id = 1
                              AND iu.product_id NOT IN (
                                  SELECT uss.product_id
                                  FROM untracked_serial_sales uss
                                  GROUP BY uss.product_id
                                  HAVING SUM(uss.quantity) >= (
                                      SELECT COUNT(*) FROM inventory_units
                                      WHERE sold = FALSE AND is_damaged = FALSE AND serial_number != 'NOSER'
                                        AND product_id = uss.product_id
                                  )
                              )
                            ORDER BY iu.serial_assigned_at ASC
                            LIMIT 1
                        """)).fetchone()

                        if not row:
                            print(f"[WARNING] Only assigned {inserted_count} SSDs for fallback — short by {total_qty - inserted_count}")
                            break

                        conn.execute(text("""
                            INSERT INTO untracked_serial_sales (product_id, order_id, quantity, created_at)
                            VALUES (:product_id, :order_id, 1, :created_at)
                        """), {
                            "product_id": row.product_id,
                            "order_id": order_id,
                            "created_at": shipped_time
                        })

                        inserted_count += 1

                    expected_serials_total = total_qty  # Adjust so the rest of processing proceeds

                else:
                    print(f"[MANUAL REVIEW] Serial count mismatch — Order {order_id}, SKU totals: {sku_quantities}, expected serials: {expected_serials_total}, received: {len(serials)}")
                    # Insert manual review per SKU
                    inserted = set()
                    for sku, _ in sku_quantities:
                        if (order_id, sku) in inserted:
                            continue
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
                    continue  # Skip rest of processing for this order



            # --- 3. Validate all serials exist and sold = False ---
            all_valid = True
            for s in serials:
                res = conn.execute(text("""
                    SELECT sold FROM inventory_units WHERE serial_number = :serial
                """), {"serial": s}).fetchone()
                if not res:
                    print(f"[MANUAL REVIEW] Serial {s} not found in inventory_units for Order {order_id}")
                    all_valid = False
                    break
                if res.sold:
                    print(f"[MANUAL REVIEW] Serial {s} already sold for Order {order_id}")
                    all_valid = False
                    break

            if not all_valid:
                # Insert manual review for all SKUs in order
                inserted = set()
                for sku, _ in sku_quantities:
                    if (order_id, sku) in inserted:
                        continue
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
                continue  # Skip processing this order

            # --- 4. All valid: assign serials to SKUs and insert logs ---
            serial_pointer = 0
            for allocation in order.get("allocations", []):
                for item in allocation.get("line_items", []):
                    sku = item.get("sellable", {}).get("sku_code")
                    quantity = item.get("quantity", 0)
                    sku_lower = (sku or "").lower()
                    is_512gb_enhanced = any(k in sku_lower for k in ["+512gb", "--512gb"])
                    expected_serials = quantity * (2 if is_512gb_enhanced else 1)

                    for _ in range(expected_serials):
                        serial = serials[serial_pointer]
                        serial_pointer += 1

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

                        conn.execute(text("""
                            UPDATE inventory_units SET sold = TRUE WHERE serial_number = :serial
                        """), {"serial": serial})

                        updated.append({"serial": serial, "order_id": order_id})

            # --- 5. SSD logic for orders shipped on/after cutoff and not return orders ---
            is_return_order = conn.execute(text("""
                SELECT 1
                FROM returns r
                JOIN inventory_units iu ON r.original_unit_id = iu.unit_id
                JOIN inventory_log il ON il.serial_number = iu.serial_number
                WHERE il.order_id = :order_id
                LIMIT 1
            """), {"order_id": order_id}).fetchone()

            if shipped_time >= ssd_cutoff and not is_return_order:
                total_ssds_needed = sum(
                    item.get("quantity", 0)
                    for allocation in order.get("allocations", [])
                    for item in allocation.get("line_items", [])
                    if any(keyword in (item.get("sellable", {}).get("sku_code") or "").lower() for keyword in ["+1tb", "--1tb", "b0d1d5j1j1"])

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

                        for ssd_row in ssd_rows:
                            ssd_serial = ssd_row.serial_number

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

            # --- 6. Report unused serials if any ---
            if serial_pointer < len(serials):
                unassigned = serials[serial_pointer:]
                print(f"[INFO] Unused serials for order {order_id}: {unassigned}")

             # --- 7. Ensure soft allocation for 1TB SSDs ---
            if shipped_time >= ssd_cutoff and not is_return_order:
                # Count how many 1TB SSDs are still needed (already handled some above)
                total_1tb_needed = sum(
                    item.get("quantity", 0)
                    for allocation in order.get("allocations", [])
                    for item in allocation.get("line_items", [])
                    if any(k in (item.get("sellable", {}).get("sku_code") or "").lower() for k in ["+1tb", "--1tb", "b0d1d5j1j1"])
                )

                # Skip if already hard-allocated all
                already_allocated = conn.execute(text("""
                    SELECT COUNT(*) FROM inventory_log il
                    JOIN inventory_units iu ON il.serial_number = iu.serial_number
                    JOIN products p ON iu.product_id = p.product_id
                    WHERE il.order_id = :order_id AND p.ssd_id = 2
                """), {"order_id": order_id}).scalar()

                soft_qty_to_allocate = total_1tb_needed - already_allocated
                if soft_qty_to_allocate > 0:
                    print(f"[INFO] Trying soft allocation of {soft_qty_to_allocate} SSDs for Order {order_id}")
                    available_products = get_available_products_by_ssd(conn, ssd_id=2)
                    to_allocate = soft_qty_to_allocate

                    for p in available_products:
                        if to_allocate <= 0:
                            break
                        qty = min(to_allocate, p["available"])
                        conn.execute(text("""
                            INSERT INTO untracked_serial_sales (product_id, order_id, quantity, created_at)
                            VALUES (:product_id, :order_id, :qty, :created_at)
                            ON CONFLICT (product_id, order_id) DO UPDATE
                            SET quantity = untracked_serial_sales.quantity + EXCLUDED.quantity
                        """), {
                            "product_id": p["product_id"],
                            "order_id": order_id,
                            "qty": qty,
                            "created_at": shipped_time
                        })
                        to_allocate -= qty

                    if to_allocate > 0:
                        print(f"[MANUAL REVIEW] Could not soft allocate {to_allocate} SSDs for Order {order_id}")
                        conn.execute(text("""
                            INSERT INTO manual_review (order_id, sku, reason, metadata, created_at)
                            VALUES (:order_id, 'SSD-1TB', 'Soft allocation failed', :metadata, :created_at)
                        """), {
                            "order_id": order_id,
                            "metadata": json.dumps({
                                "ssd_id": 2,
                                "requested": soft_qty_to_allocate,
                                "allocated": soft_qty_to_allocate - to_allocate,
                                "unallocated": to_allocate
                            }),
                            "created_at": shipped_time
                        })

    return updated
