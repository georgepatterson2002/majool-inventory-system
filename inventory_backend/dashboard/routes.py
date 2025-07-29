from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from inventory_backend.database import engine
from typing import Optional
import os
import requests
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse
import pytz
from .sync_logic import sync_veeqo_orders_job

from fastapi.responses import StreamingResponse
import io
import csv
import traceback

class PriceUpdate(BaseModel):
    product_id: int
    price: Optional[float]

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
                iu.is_damaged,
                iu.po_number
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
            "is_damaged": row.is_damaged,
            "po_number": row.po_number  # <-- add this line
        }

@router.get("/insights/monthly-report")
def download_monthly_report(cutoff: str):
    """Generate monthly CSV summary up to the given cutoff datetime (ISO 8601 string)."""
    try:
        cutoff_time = datetime.fromisoformat(cutoff)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cutoff datetime")

    with engine.connect() as conn:
        result = conn.execute(text("""
            WITH params AS (
              SELECT 
                DATE_TRUNC('month', :cutoff_time) AS month_start,
                :cutoff_time AS cutoff
            ),
            base AS (
              SELECT 
                REPLACE(m.master_sku_id, 'MSKU-', '') AS master_sku,
                m.description,
                p.product_id,

                (
                  (
                    SELECT COUNT(*)
                    FROM inventory_units iu
                    WHERE iu.product_id = p.product_id
                      AND iu.sold = FALSE
                      AND iu.is_damaged = FALSE
                      AND iu.serial_number != 'NOSER'
                  )
                  -
                  COALESCE((
                    SELECT SUM(quantity)
                    FROM untracked_serial_sales uss
                    WHERE uss.product_id = p.product_id
                  ), 0)
                ) AS qty,

                (
                  SELECT COUNT(*)
                  FROM inventory_units iu
                  WHERE iu.product_id = p.product_id
                    AND iu.sold = FALSE
                    AND iu.is_damaged = TRUE
                ) AS damaged,

                (
                  SELECT COUNT(*)
                  FROM reconciled_items ri
                  WHERE ri.product_id = p.product_id
                ) AS reconciled,

                (
                  SELECT COUNT(*)
                  FROM inventory_units iu, params
                  WHERE iu.product_id = p.product_id
                    AND iu.serial_assigned_at >= params.month_start
                    AND iu.serial_assigned_at < params.cutoff
                ) +
                (
                  SELECT COUNT(*)
                  FROM returns r, params
                  WHERE r.product_id = p.product_id
                    AND r.return_date >= params.month_start
                    AND r.return_date < params.cutoff
                ) AS quantity_received,

                (
                  SELECT COUNT(*)
                  FROM inventory_log il
                  JOIN inventory_units iu ON il.serial_number = iu.serial_number
                  JOIN params ON TRUE
                  WHERE iu.product_id = p.product_id
                    AND il.event_time >= params.month_start
                    AND il.event_time < params.cutoff
                ) AS quantity_sold

              FROM products p
              JOIN master_skus m ON p.master_sku_id = m.master_sku_id
            ),
            final AS (
              SELECT 
                master_sku,
                MAX(description) AS description,
                SUM(qty) AS qty,
                SUM(damaged) AS damaged,
                SUM(reconciled) AS reconciled,
                SUM(quantity_received) AS quantity_received,
                SUM(quantity_sold) AS quantity_sold,
                GREATEST(0, SUM(qty) + SUM(quantity_sold) - SUM(quantity_received)) AS quantity_last_month,
                (SUM(qty) + SUM(damaged) + SUM(reconciled)) AS total
              FROM base
              GROUP BY master_sku
              HAVING 
                SUM(qty + damaged + reconciled + quantity_received + quantity_sold) > 0
            )
            SELECT 
              master_sku,
              description,
              quantity_last_month,
              quantity_received,
              quantity_sold,
              qty,
              damaged,
              reconciled,
              total
            FROM final
            ORDER BY master_sku;
        """), {"cutoff_time": cutoff_time})

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(result.keys())
        writer.writerows(result.fetchall())

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=monthly_report.csv"}
        )

@router.get("/sku-breakdown")
def get_sku_breakdown(master_sku_id: str):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                WITH raw AS (
                    SELECT 
                        CASE 
                          WHEN iu.is_damaged = TRUE THEN 'Damaged'
                          ELSE p.part_number
                        END AS sku_group,
                        p.product_id,
                        p.price
                    FROM inventory_units iu
                    JOIN products p ON iu.product_id = p.product_id
                    WHERE p.master_sku_id = :msku
                      AND iu.sold = FALSE
                      AND iu.serial_number != 'NOSER'
                ),
                soft_alloc AS (
                    SELECT 
                        product_id,
                        SUM(quantity) AS soft_qty
                    FROM untracked_serial_sales
                    GROUP BY product_id
                ),
                counted AS (
                    SELECT 
                        r.sku_group,
                        r.product_id,
                        r.price,
                        COUNT(*) AS raw_qty,
                        COALESCE(SUM(sa.soft_qty), 0) AS total_soft
                    FROM raw r
                    LEFT JOIN soft_alloc sa ON r.product_id = sa.product_id
                    GROUP BY r.sku_group, r.product_id, r.price
                )
                SELECT 
                    sku_group AS sku,
                    raw_qty - total_soft AS qty,
                    product_id,
                    price
                FROM counted
                WHERE raw_qty - total_soft > 0
                ORDER BY sku
            """), {"msku": master_sku_id})

            rows = result.fetchall()
            if not rows:
                raise HTTPException(status_code=404, detail="No SKU breakdown found.")

            return [
                {
                    "sku": row.sku,
                    "qty": row.qty,
                    "product_id": row.product_id,
                    "price": float(row.price) if row.price is not None else None
                } for row in rows
            ]

    except Exception as e:
        print(f"Error in /dashboard/sku-breakdown: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve SKU breakdown")

@router.post("/product-price")
async def update_price(req: Request):
    try:
        data = await req.json()
        product_id = data.get("product_id")
        price = data.get("price")

        if product_id is None:
            raise HTTPException(status_code=400, detail="Missing product_id")

        # Skip update if no price provided
        if price is None:
            return {"status": "skipped", "reason": "No price provided"}

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE products SET price = :price WHERE product_id = :pid"),
                {"pid": product_id, "price": price}
            )

        return {"status": "ok", "product_id": product_id, "price": price}

    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")