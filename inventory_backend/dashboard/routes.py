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
                iu.serial_number,
                iu.po_number,
                iu.serial_assigned_at,
                iu.is_damaged
            FROM products p
            JOIN master_skus m ON p.master_sku_id = m.master_sku_id
            LEFT JOIN inventory_units iu ON p.product_id = iu.product_id AND iu.sold = FALSE
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