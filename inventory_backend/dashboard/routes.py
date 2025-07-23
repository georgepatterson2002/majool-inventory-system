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
            WITH base AS (
                SELECT 
                    m.master_sku_id,
                    m.description,
                    p.product_id,
                    p.product_name,
                    p.part_number,
                    p.brand,
                    (
                        (
                            SELECT COUNT(*) 
                            FROM inventory_units iu
                            WHERE iu.product_id = p.product_id
                            AND iu.sold = FALSE
                            AND iu.serial_number != 'NOSER'
                        )
                        -
                        COALESCE(
                            (
                                SELECT SUM(quantity)
                                FROM untracked_serial_sales uss
                                WHERE uss.product_id = p.product_id
                            ), 
                            0
                        )
                    ) AS quantity
                FROM products p
                JOIN master_skus m ON p.master_sku_id = m.master_sku_id
            )
            SELECT * FROM base
            WHERE quantity > 0
            ORDER BY master_sku_id, product_id;
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
                LIMIT 50
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
    updated = sync_veeqo_orders_job()
    return {
        "status": "synced",
        "serials_updated": updated,
        "count": len(updated)
    }

@router.get("/insights/po-details")
def get_po_details(po_number: str):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                p.part_number AS sku,
                p.product_name,
                iu.po_number,
                iu.serial_number,
                iu.serial_assigned_at::date AS received_date
            FROM inventory_units iu
            JOIN products p ON iu.product_id = p.product_id
            WHERE iu.po_number = :po

            UNION ALL

            SELECT 
                p.part_number AS sku,
                p.product_name,
                r.po_number,
                r.serial_number,
                r.serial_assigned_at::date AS received_date
            FROM returns r
            JOIN products p ON r.product_id = p.product_id
            WHERE r.po_number = :po

            ORDER BY sku, received_date, serial_number
        """), {"po": po_number}).fetchall()

        data = {}
        for row in result:
            key = (row.sku, row.product_name, row.received_date)
            if key not in data:
                data[key] = []
            data[key].append(row.serial_number)

        return [
            {
                "sku": sku,
                "product_name": name,
                "received_date": str(date),
                "serials": serials
            }
            for (sku, name, date), serials in data.items()
        ]

@router.get("/insights/unit-details")
def get_unit_details(serial_number: str):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT 
                p.part_number AS sku,
                p.product_name,
                iu.serial_assigned_at::date AS received_date,
                iu.sold,
                iu.is_damaged
            FROM inventory_units iu
            JOIN products p ON iu.product_id = p.product_id
            WHERE iu.serial_number = :sn
        """), {"sn": serial_number}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Serial number not found")

        return {
            "sku": row.sku,
            "product_name": row.product_name,
            "received_date": str(row.received_date),
            "sold": row.sold,
            "is_damaged": row.is_damaged
        }

