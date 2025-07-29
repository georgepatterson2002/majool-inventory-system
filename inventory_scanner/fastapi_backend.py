from fastapi import FastAPI, HTTPException, Body
from sqlalchemy import create_engine, text
from pydantic import BaseModel
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env")

engine = create_engine(DATABASE_URL)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/db-ping")
def db_ping():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        return {"db": "connected", "result": result.scalar()}

@app.post("/login")
def login(req: LoginRequest):
    query = text("SELECT password_hash FROM users WHERE username = :username")
    with engine.connect() as conn:
        result = conn.execute(query, {"username": req.username}).fetchone()
        if result and pwd_context.verify(req.password, result.password_hash):
            user_id_result = conn.execute(
                text("SELECT user_id FROM users WHERE username = :username"),
                {"username": req.username}
            ).fetchone()
            return {"success": True, "user_id": user_id_result.user_id}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/noser-units")
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
            result = conn.execute(query).mappings().all()  # fix here
            return result
    except Exception as e:
        print("❌ ERROR in /noser-units:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/assign-serial")
def assign_serial(
    unit_id: int = Body(...),
    new_serial: str = Body(...),
    user_id: int = Body(...)
):
    print(f"User {user_id} assigning serial '{new_serial}' → unit {unit_id}")
    try:
        with engine.begin() as conn:  # begin() auto-commits
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

            print(f"Updated rows: {result.rowcount}")
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Unit not found.")

            return {"success": True}
    except Exception as e:
        print("ERROR in /assign-serial:", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")
