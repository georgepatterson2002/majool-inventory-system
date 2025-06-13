from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import text
from ..database import engine
from ..security import verify_password
import traceback
import re

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

class NewProduct(BaseModel):
    part_number: str
    product_name: str
    brand: int
    master_sku_id: str
    category_id: int

class ResolveRequest(BaseModel):
    order_id: str
    sku: str
    user_id: int

class FixSerialStatusRequest(BaseModel):
    serial_number: str

class LogSaleRequest(BaseModel):
    serial_number: str
    order_id: str    

@router.get("/ping")
def scanner_ping():
    return {"scanner": "pong"}

@router.get("/db-ping")
def db_ping():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        return {"db": "connected", "result": result.scalar()}

@router.post("/login")
def login(req: LoginRequest):
    query = text("""
        SELECT user_id, password_hash, is_admin
        FROM users
        WHERE username = :username
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"username": req.username}).fetchone()
        if result and verify_password(req.password, result.password_hash):
            return {
                "success": True,
                "user_id": result.user_id,
                "is_admin": result.is_admin
            }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/noser-units")
def get_noser_units():
    try:
        query = text("""
            SELECT 
                iu.unit_id,
                iu.serial_number,
                iu.po_number,
                iu.sn_prefix,
                p.product_name,
                p.part_number,
                p.brand,
                c.name AS category,
                m.master_sku_id,
                m.description AS master_description
            FROM inventory_units iu
            JOIN products p ON iu.product_id = p.product_id
            JOIN categories c ON p.category_id = c.category_id
            JOIN master_skus m ON p.master_sku_id = m.master_sku_id
            WHERE iu.serial_number = 'NOSER'
            ORDER BY iu.unit_id DESC
        """)
        with engine.connect() as conn:
            result = conn.execute(query).mappings().all()
            return result
    except Exception as e:
        print("ERROR in /noser-units:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/assign-serial")
def assign_serial(
    unit_id: int = Body(...),
    new_serial: str = Body(...),
    user_id: int = Body(...)
):
    print(f"User {user_id} assigning serial '{new_serial}' -> unit {unit_id}")

    try:
        with engine.begin() as conn:
            # Step 1: Check if serial already exists
            existing = conn.execute(
                text("SELECT 1 FROM inventory_units WHERE serial_number = :sn"),
                {"sn": new_serial}
            ).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Serial number already exists.")

            # Step 2: Get required SN prefix for this unit
            result = conn.execute(
                text("SELECT sn_prefix FROM inventory_units WHERE unit_id = :unit_id"),
                {"unit_id": unit_id}
            ).fetchone()

            if result is None:
                raise HTTPException(status_code=404, detail="Unit not found.")

            sn_prefix = result.sn_prefix

            # Step 3: Validate prefix match if required
            if sn_prefix and not new_serial.upper().startswith(sn_prefix.upper()):
                raise HTTPException(
                    status_code=400,
                    detail=f"Serial must start with '{sn_prefix}'"
                )

            # Step 4: Assign the serial
            conn.execute(
                text("""
                    UPDATE inventory_units
                    SET serial_number       = :sn,
                        assigned_by_user_id = :user_id,
                        serial_assigned_at  = NOW()
                    WHERE unit_id = :unit_id
                """),
                {"sn": new_serial, "user_id": user_id, "unit_id": unit_id}
            )


            return {"success": True}

    except HTTPException:
        raise  # re-raise known HTTP errors

    except Exception as e:
        print("ERROR in /assign-serial:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")



@router.get("/products")
def get_product_list():
    try:
        query = text("""
            SELECT 
                p.product_id,
                p.product_name,
                p.part_number,
                p.brand,
                c.name AS category,
                m.master_sku_id,
                m.description AS master_description
            FROM products p
            JOIN categories c ON p.category_id = c.category_id
            JOIN master_skus m ON p.master_sku_id = m.master_sku_id
            ORDER BY m.master_sku_id, p.part_number
        """)
        with engine.connect() as conn:
            result = conn.execute(query).mappings().all()
            return result
    except Exception as e:
        print("ERROR in /products:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/add-delivery")
def add_delivery(
    product_id: int = Body(...),
    quantity: int = Body(...),
    user_id: int = Body(...),
    po_number: str = Body(...),
    sn_prefix: str = Body(default=None)
):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero.")

    if not po_number or len(po_number) < 3:
        raise HTTPException(status_code=400, detail="PO number is required.")

    if po_number.startswith("11-") or po_number.count("-") >= 2:
        raise HTTPException(status_code=400, detail="That looks like an Order ID, not a PO number.")

    if sn_prefix and (len(sn_prefix) != 2 or not re.match(r"^[A-Z0-9]{2}$", sn_prefix, re.IGNORECASE)):
        raise HTTPException(status_code=400, detail="SN prefix must be 2 alphanumeric characters.")

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO inventory_units (product_id, serial_number, po_number, sn_prefix)
                    SELECT :product_id, 'NOSER', :po_number, :sn_prefix
                    FROM generate_series(1, :qty)
                """),
                {"product_id": product_id, "qty": quantity, "po_number": po_number, "sn_prefix": sn_prefix}
            )

        return {"success": True}

    except Exception as e:
        print("ERROR in /add-delivery:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


def submit_product(self):
    from app.api_client import add_product

    part_number = self.part_number_input.text().strip()
    product_name = self.product_name_input.text().strip()
    brand = self.brand_input.text().strip()
    master_sku_id = self.master_sku_dropdown.currentData()
    category_id = self.category_dropdown.currentData()

    if not part_number or not product_name or not brand:
        QMessageBox.warning(self, "Missing Fields", "Please fill in all fields.")
        return

    result = add_product(part_number, product_name, brand, master_sku_id, category_id)

    if result["success"]:
        QMessageBox.information(self, "Success", "Product added.")
        self.toggle_mode()       # return to scanner
        self.load_data()         # refresh NOSER
    else:
        QMessageBox.critical(self, "Error", f"Failed: {result['detail']}")

@router.get("/categories")
def get_categories():
    try:
        query = text("""
            SELECT category_id, name
            FROM categories
            ORDER BY name
        """)
        with engine.connect() as conn:
            result = conn.execute(query).mappings().all()
            return result
    except Exception as e:
        print("ERROR in /categories:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/brands")
def get_brands():
    try:
        query = text("""
            SELECT brand_id, brand_name
            FROM brands
            ORDER BY brand_name
        """)
        with engine.connect() as conn:
            result = conn.execute(query).mappings().all()
            return result
    except Exception as e:
        print("ERROR in /brands:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/add-product")
def add_product(data: NewProduct):
    try:
        # Check for duplicate SKU
        with engine.connect() as conn:
            check = conn.execute(
                text("SELECT 1 FROM products WHERE part_number = :sku"),
                {"sku": data.part_number}
            ).fetchone()

            if check:
                raise HTTPException(status_code=400, detail="Product already exists.")

        # Insert new product
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO products (part_number, product_name, brand, master_sku_id, category_id)
                    VALUES (:pn, :name, :brand, :msku, :cat)
                """),
                {
                    "pn": data.part_number,
                    "name": data.product_name,
                    "brand": data.brand,
                    "msku": data.master_sku_id,
                    "cat": data.category_id
                }
            )

        return {"success": True}
    except Exception as e:
        print("ERROR in /add-product:", str(e))
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/master-skus")
def get_master_skus():
        try:
            query = text("""
                         SELECT master_sku_id, description
                         FROM master_skus
                         ORDER BY master_sku_id
                         """)
            with engine.connect() as conn:
                result = conn.execute(query).mappings().all()
                return result
        except Exception as e:
            print("ERROR in /master-skus:", str(e))
            raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/manual-review")
def get_manual_review(resolved: bool = False):
    try:
        query = text("""
            SELECT review_id, order_id, sku, created_at
            FROM manual_review
            WHERE resolved = :resolved
            ORDER BY created_at DESC
        """)
        with engine.connect() as conn:
            result = conn.execute(query, {"resolved": resolved}).mappings().all()
            return result
    except Exception as e:
        print("ERROR in /manual-review:",str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/manual-review/resolve")
def resolve_manual_review(req: ResolveRequest):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE manual_review
                    SET resolved = TRUE,
                    resolved_by_user_id = :uid
                    WHERE order_id = :oid AND sku = :sku AND resolved = FALSE
                """),
                {"uid": req.user_id, "oid": req.order_id, "sku": req.sku}
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Review not found or already resolved")

        return {"success": True}
    except Exception as e:
        print("ERROR in /manual-review/resolve:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    
@router.post("/fix-serial-status")
def fix_serial_status(req: FixSerialStatusRequest):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("UPDATE inventory_units SET sold = TRUE WHERE serial_number = :sn"),
                {"sn": req.serial_number}
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Serial number not found")

        return {"success": True}

    except Exception as e:
        print("ERROR in /fix-serial-status:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.post("/insert-inventory-log")
def insert_inventory_log(req: LogSaleRequest):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO inventory_log (sku, serial_number, order_id)
                    SELECT p.part_number, iu.serial_number, :order_id
                    FROM inventory_units iu
                    JOIN products p ON iu.product_id = p.product_id
                    WHERE iu.serial_number = :sn
                """),
                {"sn": req.serial_number, "order_id": req.order_id}
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Serial number not found or product join failed")

        return {"success": True}

    except Exception as e:
        print("ERROR in /insert-inventory-log:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.post("/handle-return-scan")
def handle_return_scan(
    scanned_serial: str = Body(...),
    placeholder_unit_id: int = Body(...),
    user_id: int = Body(...)
):
    try:
        with engine.begin() as conn:
            # Step 1: Find the existing unit by serial
            original = conn.execute(text("""
                SELECT iu.unit_id, iu.product_id, iu.serial_number, iu.serial_assigned_at,
                       iu.assigned_by_user_id, iu.po_number, iu.sn_prefix, iu.sold,
                       m.master_sku_id
                FROM inventory_units iu
                JOIN products p ON iu.product_id = p.product_id
                JOIN master_skus m ON p.master_sku_id = m.master_sku_id
                WHERE iu.serial_number = :sn
            """), {"sn": scanned_serial}).fetchone()

            if not original:
                raise HTTPException(status_code=404, detail="Serial number not found.")

            if not original.sold:
                raise HTTPException(status_code=400, detail="Serial number is already in stock.")

            # Step 2: Verify master SKU match
            placeholder = conn.execute(text("""
                SELECT iu.unit_id, p.product_id, m.master_sku_id
                FROM inventory_units iu
                JOIN products p ON iu.product_id = p.product_id
                JOIN master_skus m ON p.master_sku_id = m.master_sku_id
                WHERE iu.unit_id = :unit_id AND iu.serial_number = 'NOSER'
            """), {"unit_id": placeholder_unit_id}).fetchone()

            if not placeholder:
                raise HTTPException(status_code=400, detail="Placeholder NOSER unit not found.")

            if placeholder.master_sku_id != original.master_sku_id:
                raise HTTPException(status_code=400, detail="Master SKU mismatch between scanned unit and placeholder.")

            # Step 3: Archive original unit to returns table
            conn.execute(text("""
                INSERT INTO returns (
                    original_unit_id, product_id, serial_number, serial_assigned_at,
                    assigned_by_user_id, po_number, sn_prefix, sold
                ) VALUES (
                    :original_unit_id, :product_id, :serial_number, :serial_assigned_at,
                    :assigned_by_user_id, :po_number, :sn_prefix, :sold
                )
            """), {
                "original_unit_id": original.unit_id,
                "product_id": original.product_id,
                "serial_number": original.serial_number,
                "serial_assigned_at": original.serial_assigned_at,
                "assigned_by_user_id": original.assigned_by_user_id,
                "po_number": original.po_number,
                "sn_prefix": original.sn_prefix,
                "sold": original.sold
            })

            # Step 4: Update original unit as returned
            conn.execute(text("""
                UPDATE inventory_units
                SET sold = FALSE,
                    serial_assigned_at = NOW(),
                    po_number = 'RETURN'
                WHERE unit_id = :unit_id
            """), {"unit_id": original.unit_id})

            # Step 5: Remove the NOSER placeholder
            conn.execute(text("""
                DELETE FROM inventory_units WHERE unit_id = :uid
            """), {"uid": placeholder.unit_id})

        return {"success": True, "message": "Return processed successfully."}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR in /handle-return-scan:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    