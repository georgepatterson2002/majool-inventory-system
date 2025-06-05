from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from inventory_backend.database import engine
import os
import requests
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse
import pytz
from .sync_logic import sync_veeqo_orders_job



router = APIRouter()

VEEQO_API_KEY = os.getenv("VEEQO_API_KEY")
if not VEEQO_API_KEY:
    raise RuntimeError("Missing VEEQO_API_KEY in environment")


@router.get("/ping")
def dashboard_ping():
    return {"dashboard": "pong"}


@router.get("/products")
def get_products():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM view_product_stock_summary"))
        rows = result.fetchall()
        keys = result.keys()
        return [dict(zip(keys, row)) for row in rows]


@router.get("/grouped-products")
def get_grouped_products():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                m.master_sku_id,
                m.description,
                p.product_id,
                p.product_name,
                p.part_number,
                p.brand,
                iu.serial_number
            FROM products p
            JOIN master_skus m ON p.master_sku_id = m.master_sku_id
            LEFT JOIN inventory_units iu ON p.product_id = iu.product_id
        """))
        rows = result.fetchall()
        keys = result.keys()
        return [dict(zip(keys, row)) for row in rows]


@router.get("/manual-check")
def get_manual_check_items():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT review_id AS id, order_id, sku, created_at
                FROM manual_review
                WHERE resolved = FALSE
                ORDER BY created_at DESC
                LIMIT 100
            """))
            rows = result.fetchall()
            keys = result.keys()
            return [dict(zip(keys, row)) for row in rows]
    except Exception as e:
        print("Manual check failed:", e)
        return JSONResponse(status_code=500, content={"error": str(e)})



@router.get("/inventory-log")
def get_inventory_log():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT sku, serial_number, order_id, event_time
            FROM inventory_log
            ORDER BY event_time DESC
            LIMIT 100
        """))
        rows = result.fetchall()
        keys = result.keys()
        return [dict(zip(keys, row)) for row in rows]

@router.post("/sync-veeqo-orders")
def sync_veeqo_orders():
    def fetch_veeqo_orders_shipped_today():
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
        if response.status_code != 200:
            raise Exception(f"Veeqo API Error: {response.status_code} - {response.text}")

        orders = response.json()

        shipped_today = [
            o for o in orders
            if o.get("shipped_at") and
               datetime.fromisoformat(o["shipped_at"].replace("Z", "+00:00")) >= today
        ]

        return shipped_today

    orders = fetch_veeqo_orders_shipped_today()
    updated = []

    with engine.begin() as conn:
        for order in orders:
            if order.get("status") != "shipped":
                continue

            shipped_time = order.get("shipped_at")
            if not shipped_time:
                continue

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
                                "order_id": order.get("number"),
                                "sku": sku,
                                "created_at": shipped_time
                            })
                        continue

                    for serial in serials[:quantity]:
                        result = conn.execute(
                            text("""
                                INSERT INTO inventory_log (sku, serial_number, order_id, event_time)
                                VALUES (:sku, :serial, :order_id, :event_time)
                                ON CONFLICT (serial_number) DO NOTHING
                                RETURNING serial_number
                            """),
                            {
                                "sku": sku,
                                "serial": serial,
                                "order_id": order.get("number"),
                                "event_time": shipped_time
                            }
                        )

                        if result.fetchone():
                            updated.append({
                                "serial": serial,
                                "order_id": order.get("number")
                            })

                            conn.execute(
                                text("DELETE FROM inventory_units WHERE serial_number = :serial"),
                                {"serial": serial}
                            )

    print("Veeqo Sync Complete")
    return {
        "status": "synced",
        "serials_updated": updated,
        "count": len(updated)
    }

@router.post("/sync-veeqo-orders")
def sync_veeqo_orders():
    updated = sync_veeqo_orders_job()
    return {
        "status": "synced",
        "serials_updated": updated,
        "count": len(updated)
    }