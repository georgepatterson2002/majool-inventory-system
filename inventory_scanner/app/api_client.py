import os
from dotenv import load_dotenv
import requests

# Load .env file from the root directory
load_dotenv()

# Get API base URL from .env
API_BASE_URL = os.getenv("API_BASE_URL")

def ping_server():
    try:
        r = requests.get(f"{API_BASE_URL}/ping", timeout=3)
        return r.status_code == 200
    except Exception as e:
        print(f"Ping failed: {e}")
        return False

def login_user(username, password):
    try:
        r = requests.post(
            f"{API_BASE_URL}/login",
            json={"username": username, "password": password},
            timeout=5
        )
        print("Login response:", r.status_code, r.text)
        if r.status_code == 200:
            return r.json()  # return full JSON with user_id
        else:
            return {"success": False, "detail": r.text}
    except Exception as e:
        print(f"Login failed: {e}")
        return {"success": False, "detail": str(e)}

def fetch_product_list():
    try:
        r = requests.get(f"{API_BASE_URL}/products")
        if r.status_code == 200:
            return r.json()
        else:
            print("Failed to fetch product list:", r.text)
            return []
    except Exception as e:
        print("Error fetching products:", e)
        return []

def add_delivery(product_id, quantity, user_id):
    try:
        r = requests.post(
            f"{API_BASE_URL}/add-delivery",
            json={
                "product_id": product_id,
                "quantity": quantity,
                "user_id": user_id
            }
        )
        if r.status_code == 200:
            return {"success": True}
        else:
            return {"success": False, "detail": r.json().get("detail", "Unknown error")}
    except Exception as e:
        print("Delivery failed:", e)
        return {"success": False, "detail": str(e)}

def fetch_master_skus():
    try:
        r = requests.get(f"{API_BASE_URL}/master-skus")
        if r.status_code == 200:
            return r.json()
        else:
            return []
    except Exception as e:
        print("Failed to fetch master SKUs:", e)
        return []

def fetch_categories():
    try:
        r = requests.get(f"{API_BASE_URL}/categories")
        if r.status_code == 200:
            return r.json()
        else:
            return []
    except Exception as e:
        print("Failed to fetch categories:", e)
        return []

def add_product(part_number, product_name, brand, master_sku_id, category_id):
    payload = {
        "part_number": part_number,
        "product_name": product_name,
        "brand": brand,
        "master_sku_id": master_sku_id,
        "category_id": category_id
    }

    print("🚀 Sending to backend:", payload)  # <-- THIS IS KEY

    try:
        r = requests.post(
            f"{API_BASE_URL}/add-product",
            json=payload
        )
        if r.status_code == 200:
            return {"success": True}
        else:
            print("❌ Backend response:", r.status_code, r.text)  # <-- also helpful
            return {"success": False, "detail": r.json().get("detail", "Unknown error")}
    except Exception as e:
        print("❌ Failed to add product:", e)
        return {"success": False, "detail": str(e)}
