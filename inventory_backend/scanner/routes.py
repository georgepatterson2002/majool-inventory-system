from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import text
from typing import Optional
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
    ssd_id: Optional[int] = None

class ResolveRequest(BaseModel):
    order_id: str
    sku: str
    user_id: int

class FixSerialStatusRequest(BaseModel):
    serial_number: str

class LogSaleRequest(BaseModel):
    serial_number: str
    order_id: str   

class ClearLogRequest(BaseModel):
    order_id: str

class NewMasterSKU(BaseModel):
    master_sku_id: str
    description: str

class NewUser(BaseModel):
    username: str
    password_hash: str
    is_admin: bool = False

class DisposalRequest(BaseModel):
    unit_id: int
    original_product_id: int

class RepairRequest(BaseModel):
    unit_id: int
    new_product_id: Optional[int] = None

class UpdateUnitMeta(BaseModel):
    unit_id: int
    sn_prefix: Optional[str]
    po_number: Optional[str]
    user_id: int

class BulkUpdateRequest(BaseModel):
    sn_prefix: Optional[str]
    po_number: Optional[str]
    user_id: int

class NewReconciledItem(BaseModel):
    product_id: int
    serial_number: str
    memo_number: str

class ReconcileFromExisting(BaseModel):
    serial_number: str
    memo_number: str

class DamageRequest(BaseModel):
    serial_number: str

class ResolveReconciledRequest(BaseModel):
    reconciled_id: int

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
    sn_prefix: str = Body(default=None),
    is_damaged: bool = Body(default=False)  
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
                    INSERT INTO inventory_units (product_id, serial_number, po_number, sn_prefix, is_damaged)
                    SELECT :product_id, 'NOSER', :po_number, :sn_prefix, :is_damaged
                    FROM generate_series(1, :qty)
                """),
                {
                    "product_id": product_id,
                    "qty": quantity,
                    "po_number": po_number,
                    "sn_prefix": sn_prefix,
                    "is_damaged": is_damaged 
                }
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
        with engine.begin() as conn:
            # Check for duplicate SKU
            check = conn.execute(
                text("SELECT 1 FROM products WHERE part_number = :sku"),
                {"sku": data.part_number}
            ).fetchone()

            if check:
                raise HTTPException(status_code=400, detail="Product already exists.")

            # Insert new product
            if data.ssd_id is not None:
                conn.execute(
                    text("""
                        INSERT INTO products (part_number, product_name, brand, master_sku_id, category_id, ssd_id)
                        VALUES (:pn, :name, :brand, :msku, :cat, :ssd_id)
                    """),
                    {
                        "pn": data.part_number,
                        "name": data.product_name,
                        "brand": data.brand,
                        "msku": data.master_sku_id,
                        "cat": data.category_id,
                        "ssd_id": data.ssd_id
                    }
                )
            else:
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

@router.post("/clear-inventory-log")
def clear_inventory_log(req: ClearLogRequest):
    try:
        with engine.begin() as conn:
            # Step 1: Get all serials linked to this order
            results = conn.execute(text("""
                SELECT serial_number FROM inventory_log
                WHERE order_id = :oid
            """), {"oid": req.order_id}).fetchall()

            # Step 2: Mark those serials as unsold
            for row in results:
                conn.execute(text("""
                    UPDATE inventory_units SET sold = FALSE
                    WHERE serial_number = :sn
                """), {"sn": row.serial_number})

            # Step 3: Delete from inventory_log
            conn.execute(text("""
                DELETE FROM inventory_log WHERE order_id = :oid
            """), {"oid": req.order_id})

        return {"success": True, "cleared": len(results)}

    except Exception as e:
        print("ERROR in /clear-inventory-log:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.post("/create-master-sku")
def create_master_sku(data: NewMasterSKU):
    try:
        with engine.connect() as conn:
            # Check for existing MSKU ID
            check = conn.execute(
                text("SELECT 1 FROM master_skus WHERE master_sku_id = :msku"),
                {"msku": data.master_sku_id}
            ).fetchone()

            if check:
                raise HTTPException(status_code=400, detail="Master SKU already exists.")

        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO master_skus (master_sku_id, description)
                    VALUES (:msku, :desc)
                """),
                {"msku": data.master_sku_id, "desc": data.description}
            )

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR in /create-master-sku:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.post("/create-user")
def create_user(data: NewUser):
    try:
        with engine.begin() as conn:
            # Check if username exists
            exists = conn.execute(
                text("SELECT 1 FROM users WHERE username = :u"),
                {"u": data.username}
            ).fetchone()

            if exists:
                raise HTTPException(status_code=400, detail="Username already exists.")

            conn.execute(
                text("""
                    INSERT INTO users (username, password_hash, is_admin)
                    VALUES (:u, :ph, :admin)
                """),
                {"u": data.username, "ph": data.password_hash, "admin": data.is_admin}
            )
        return {"success": True}
    except Exception as e:
        print("Create user error:", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/ssds")
def get_ssd_types():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT ssd_id, label FROM ssds ORDER BY ssd_id"))
            return result.mappings().all()
    except Exception as e:
        print("ERROR in /ssds:", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch SSD types")

@router.post("/dispose-unit")
def dispose_unit(req: DisposalRequest):
    try:
        with engine.begin() as conn:
            # Check if already disposed
            existing = conn.execute(
                text("SELECT 1 FROM disposals WHERE unit_id = :uid"),
                {"uid": req.unit_id}
            ).fetchone()

            if existing:
                raise HTTPException(status_code=400, detail="This unit is already marked as disposed.")

            # Mark unit as sold
            conn.execute(
                text("UPDATE inventory_units SET sold = TRUE WHERE unit_id = :uid"),
                {"uid": req.unit_id}
            )

            # Log disposal
            conn.execute(
                text("""
                    INSERT INTO disposals (unit_id, original_product_id)
                    VALUES (:uid, :pid)
                """),
                {"uid": req.unit_id, "pid": req.original_product_id}
            )

        return {"success": True}

    except Exception as e:
        print("ERROR in /dispose-unit:", str(e))
        raise HTTPException(status_code=500, detail="Failed to mark disposal")

@router.get("/damaged-units")
def get_damaged_units():
    try:
        query = text("""
            SELECT 
                iu.unit_id,
                iu.serial_number,
                iu.po_number,
                iu.product_id,
                p.part_number,
                p.product_name
            FROM inventory_units iu
            JOIN products p ON iu.product_id = p.product_id
            WHERE iu.is_damaged = TRUE AND iu.sold = FALSE
            ORDER BY iu.unit_id DESC
        """)
        with engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
            return list(rows)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch damaged units")


@router.post("/mark-repaired")
def mark_repaired(req: RepairRequest):
    try:
        with engine.begin() as conn:
            # 1. Look up original product_id
            original = conn.execute(
                text("SELECT product_id FROM inventory_units WHERE unit_id = :uid"),
                {"uid": req.unit_id}
            ).fetchone()

            if not original:
                raise HTTPException(status_code=404, detail="Unit not found")

            old_pid = original.product_id
            new_pid = req.new_product_id or old_pid

            # 2. Update inventory unit
            if req.new_product_id:
                conn.execute(
                    text("""
                        UPDATE inventory_units
                        SET is_damaged = FALSE,
                            product_id = :pid
                        WHERE unit_id = :uid
                    """),
                    {"uid": req.unit_id, "pid": new_pid}
                )
            else:
                conn.execute(
                    text("""
                        UPDATE inventory_units
                        SET is_damaged = FALSE
                        WHERE unit_id = :uid
                    """),
                    {"uid": req.unit_id}
                )

            # 3. Log the repair
            conn.execute(
                text("""
                    INSERT INTO repairs (unit_id, old_product_id, new_product_id)
                    VALUES (:uid, :old_pid, :new_pid)
                """),
                {"uid": req.unit_id, "old_pid": old_pid, "new_pid": new_pid}
            )

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR in /mark-repaired:", str(e))
        raise HTTPException(status_code=500, detail="Failed to mark item as repaired")

@router.post("/update-unit-meta")
def update_unit_meta(data: UpdateUnitMeta):
    try:
        fields = []
        params = {"uid": data.unit_id}

        if data.sn_prefix is not None:
            if data.sn_prefix == "":
                fields.append("sn_prefix = NULL")
            else:
                fields.append("sn_prefix = :sn_prefix")
                params["sn_prefix"] = data.sn_prefix
        if data.po_number is not None:
            fields.append("po_number = :po_number")
            params["po_number"] = data.po_number

        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update.")

        query = f"""
            UPDATE inventory_units
            SET {", ".join(fields)}
            WHERE unit_id = :uid
        """

        with engine.begin() as conn:
            result = conn.execute(text(query), params)
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Unit not found")

        return {"success": True}
    except Exception as e:
        print("ERROR in /update-unit-meta:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/bulk-update-units")
def bulk_update_units(req: BulkUpdateRequest):
    if not req.sn_prefix and not req.po_number:
        raise HTTPException(status_code=400, detail="At least one field must be provided.")

    try:
        with engine.begin() as conn:
            fields = []
            params = {}

            if req.sn_prefix is not None:
                fields.append("sn_prefix = :sn_prefix")
                params["sn_prefix"] = req.sn_prefix
            if req.po_number is not None:
                fields.append("po_number = :po_number")
                params["po_number"] = req.po_number

            if not fields:
                raise HTTPException(status_code=400, detail="Nothing to update.")

            params["user_id"] = req.user_id

            query = f"""
                UPDATE inventory_units
                SET {', '.join(fields)}
                WHERE serial_number = 'NOSER'
            """

            result = conn.execute(text(query), params)
            return {"success": True, "updated": result.rowcount}
    except Exception as e:
        print("Bulk update error:", e)
        raise HTTPException(status_code=500, detail="Bulk update failed.")

@router.get("/reconciled-items")
def get_reconciled_items():
    try:
        query = text("""
            SELECT ri.reconciled_id, ri.serial_number, p.part_number, ri.memo_number, ri.reconciled_at
            FROM reconciled_items ri
            JOIN products p ON ri.product_id = p.product_id
            WHERE ri.resolved = FALSE
            ORDER BY ri.reconciled_at DESC
        """)
        with engine.connect() as conn:
            return conn.execute(query).mappings().all()
    except Exception as e:
        print("ERROR in /reconciled-items:", str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch reconciled items")

@router.post("/reconciled-items")
def create_reconciled_item(data: NewReconciledItem):
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO reconciled_items (product_id, serial_number, memo_number)
                    VALUES (:product_id, :serial, :memo)
                """),
                {"product_id": data.product_id, "serial": data.serial_number, "memo": data.memo_number}
            )
        return {"success": True}
    except Exception as e:
        print("ERROR in POST /reconciled-items:", str(e))
        raise HTTPException(status_code=500, detail="Failed to add reconciled item")

@router.post("/reconcile-from-existing")
def reconcile_from_existing(data: ReconcileFromExisting):
    try:
        with engine.begin() as conn:
            # Lookup product by serial
            row = conn.execute(
                text("""
                    SELECT product_id FROM inventory_units
                    WHERE serial_number = :sn
                """), {"sn": data.serial_number}
            ).fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Serial not found in inventory_units")

            # Insert reconciled item
            conn.execute(
                text("""
                    INSERT INTO reconciled_items (product_id, serial_number, memo_number)
                    VALUES (:pid, :sn, :memo)
                """),
                {"pid": row.product_id, "sn": data.serial_number, "memo": data.memo_number}
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print("ERROR in /reconcile-from-existing:", str(e))
        raise HTTPException(status_code=500, detail="Failed to reconcile from existing unit")

@router.post("/reconciled-items/resolve")
def resolve_reconciled_item(req: ResolveReconciledRequest):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("UPDATE reconciled_items SET resolved = TRUE WHERE reconciled_id = :rid"),
                {"rid": req.reconciled_id}
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Reconciled item not found")
        return {"success": True}
    except Exception as e:
        print("ERROR resolving reconciled item:", str(e))
        raise HTTPException(status_code=500, detail="Failed to resolve reconciled item")

@router.post("/mark-damaged")
def mark_damaged_unit(req: DamageRequest):
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    UPDATE inventory_units
                    SET is_damaged = TRUE
                    WHERE serial_number = :sn
                """),
                {"sn": req.serial_number}
            )
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Serial number not found.")
        return {"success": True}
    except Exception as e:
        print("ERROR in /mark-damaged:", str(e))
        raise HTTPException(status_code=500, detail="Failed to mark unit as damaged")
