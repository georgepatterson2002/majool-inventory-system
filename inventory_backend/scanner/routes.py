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
    brand: str
    master_sku_id: str
    category_id: int

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
    print(f"User {user_id} assigning serial '{new_serial}' → unit {unit_id}")

    try:
        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT 1 FROM inventory_units WHERE serial_number = :sn"),
                {"sn": new_serial}
            ).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Serial number already exists.")

            result = conn.execute(
                text("""
                     UPDATE inventory_units
                     SET serial_number       = :sn,
                         assigned_by_user_id = :uid,
                         serial_assigned_at  = NOW()
                     WHERE unit_id = :unit_id
                     """),
                {"sn": new_serial, "uid": user_id, "unit_id": unit_id}
            )

            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Unit not found.")

            return {"success": True}
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
    user_id: int = Body(...)
):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero.")

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                     INSERT INTO inventory_units (product_id, serial_number)
                     SELECT :product_id, 'NOSER'
                     FROM generate_series(1, :qty)
                     """),
                {"product_id": product_id, "qty": quantity}
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
