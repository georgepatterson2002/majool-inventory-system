# Majool Inventory System

A full-stack inventory tracking system with real-time data sync, desktop scanning, and manual review workflows — built for fast-paced eCommerce and warehouse operations.

> 🚀 Used daily by warehouse and ops teams at Majool Inc.

## 🎥 System Demo

https://github.com/user-attachments/assets/e6268347-40a2-49bc-979a-b05587e0f383

*This video shows the full system workflow, including the updated scanner and dashboard features.*

---

## 🧠 What This Project Demonstrates

- End-to-end architecture (API, PostgreSQL, React, Python desktop app)
- Real-time sync with external platforms (e.g., Veeqo)
- Inventory workflows with serial tracking, return handling, and error resolution
- Role-based web dashboard for operations and admin staff
- Packaged desktop scanner app (PyInstaller) for Windows deployment
- Secure and environment-variable driven configuration
- Clean documentation and structured database schema

---

## Features

- 📦 Real-time inventory tracking across multiple platforms
- 🔄 Sync orders and product updates with external systems like Veeqo
- 🧾 Log every serial-numbered unit from delivery to sale
- 🖥️ Desktop app for scanning and assigning serial numbers, with bulk edit and error recovery tools
- 🧑‍💼 Web dashboard for admins to manage inventory, verify shipments, and run manual checks
- 📊 Insights tab with PO and serial lookup for quick audits
- 📋 Shipped log with expandable order history and serial-level detail
- 🛠️ Manual review queue with dynamic badge indicators
- 🗃️ Local backups saved daily as CSV
- 📤 One-click monthly CSV report export for reporting and reconciliation

If you're using a different fulfillment platform, you'll need to adjust the `/api/sync-veeqo-orders` route and related data processing logic accordingly.

---

## Why I Built This

As part of managing inventory workflows for Majool Inc., I saw the need for a unified system that connected product data across multiple online selling platforms, warehouse scanners, and order sync platforms. I designed this system to eliminate spreadsheet chaos, reduce inventory mismatches, and make life easier for warehouse and ops teams.

---

## 📦 Shipping Assumptions

This system assumes your orders are shipped through **Veeqo**.

The backend sync logic is built around the Veeqo API and powers several key features:

- ✅ Serial number assignment upon shipment
- 🧾 Inventory logging to `inventory_log`
- 🛠️ Flagging orders with missing serials or tracking info for manual review

---

## Tech Stack

| Layer           | Tech Used                     |
|----------------|-------------------------------|
| Backend API     | FastAPI, PostgreSQL, SQLAlchemy, Uvicorn |
| Frontend        | React, Vite, Tailwind CSS     |
| Desktop App     | Python, PyQt5, PyInstaller     |
| Dev Tools       | Git, dotenv, `.bat` scripts, NSSM, PyInstaller (EXE builds) |

---

## 🗃️ Database Schema

This system uses a normalized PostgreSQL schema to track products, inventory units, stock logs, users, and manual checks. Core tables:

### `brands`
| Column       | Type    | Description                  |
|--------------|---------|------------------------------|
| brand_id     | SERIAL  | Primary key                  |
| brand_name   | TEXT    | Unique brand name            |

### `categories`
| Column       | Type    | Description                  |
|--------------|---------|------------------------------|
| category_id  | SERIAL  | Primary key                  |
| name         | TEXT    | Unique category name         |

### `master_skus`
| Column         | Type      | Description                            |
|----------------|-----------|----------------------------------------|
| master_sku_id  | TEXT      | Primary key (no whitespace)            |
| description    | TEXT      | Description of SKU group               |
| created_at     | TIMESTAMP | Automatically set to `now()`           |

### `products`
| Column         | Type    | Description                              |
|----------------|---------|------------------------------------------|
| product_id     | SERIAL  | Primary key                              |
| master_sku_id  | TEXT    | FK to `master_skus`                      |
| part_number    | TEXT    | Unique part number                       |
| product_name   | TEXT    | Name of product                          |
| category_id    | INT     | FK to `categories`                       |
| brand          | INT     | FK to `brands`                           |
| ssd_id         | INT     | FK to `ssds`                             |

### `inventory_units`
| Column              | Type      | Description                                 |
|---------------------|-----------|---------------------------------------------|
| unit_id             | SERIAL    | Primary key                                 |
| product_id          | INT       | FK to `products`, cascades on delete        |
| serial_number       | TEXT      | Unique per unit                             |
| serial_assigned_at  | TIMESTAMP | Defaults to `now()`                         |
| assigned_by_user_id | INT       | FK to `users` (who scanned/assigned it)     |
| po_number           | TEXT      | Purchase order reference (default `UNKNOWN`)|
| sn_prefix           | VARCHAR(2)| Optional serial prefix                      |
| sold                | BOOLEAN   | Indicates sale status                       |
| is_damaged          | BOOLEAN   | Flags damaged units                         |

### `inventory_log`
| Column        | Type      | Description                      |
|---------------|-----------|----------------------------------|
| log_id        | SERIAL    | Primary key                      |
| sku           | TEXT      | SKU involved in the event        |
| serial_number | TEXT      | Optional serial                  |
| order_id      | TEXT      | Related order ID                 |
| event_time    | TIMESTAMP | Defaults to `CURRENT_TIMESTAMP` |

### `manual_review`
| Column     | Type      | Description                            |
|------------|-----------|----------------------------------------|
| review_id  | SERIAL    | Primary key                            |
| order_id   | TEXT      | Order flagged for manual check         |
| sku        | TEXT      | SKU under review                       |
| created_at | TIMESTAMP | Defaults to `CURRENT_TIMESTAMP`        |
| resolved   | BOOLEAN   | Indicates if resolved                  |
| resolved_by_user_id | INT | FK to `users` (if resolved)        |

### `returns`
| Column              | Type      | Description                              |
|---------------------|-----------|------------------------------------------|
| return_id           | SERIAL    | Primary key                              |
| original_unit_id    | INT       | FK to `inventory_units`                  |
| product_id          | INT       | FK to `products`                         |
| serial_number       | TEXT      | Returned serial                          |
| serial_assigned_at  | TIMESTAMP | When it was originally scanned           |
| assigned_by_user_id | INT       | User who processed return                |
| po_number           | TEXT      | Purchase order number                    |
| sn_prefix           | VARCHAR(2)| Serial prefix                            |
| sold                | BOOLEAN   | Whether it was sold before return        |
| return_date         | TIMESTAMP | Defaults to `CURRENT_TIMESTAMP`          |

### `repairs`
| Column              | Type      | Description                              |
|---------------------|-----------|------------------------------------------|
| repair_id           | SERIAL    | Primary key                              |
| unit_id             | INT       | FK to `inventory_units`                  |
| old_product_id      | INT       | Original product before repair           |
| new_product_id      | INT       | Updated product after repair             |
| repaired_at         | TIMESTAMP | Defaults to `CURRENT_TIMESTAMP`          |

### `disposals`
| Column              | Type      | Description                              |
|---------------------|-----------|------------------------------------------|
| disposal_id         | SERIAL    | Primary key                              |
| unit_id             | INT       | FK to `inventory_units`                  |
| original_product_id | INT       | Product being disposed                   |
| disposed_at         | TIMESTAMP | Defaults to `CURRENT_TIMESTAMP`          |

### `reconciled_items`
| Column        | Type      | Description                      |
|---------------|-----------|----------------------------------|
| reconciled_id | SERIAL    | Primary key                      |
| product_id    | INT       | FK to `products`                 |
| serial_number | TEXT      | Reconciled serial                |
| memo_number   | TEXT      | Reference memo                   |
| reconciled_at | TIMESTAMP | Defaults to `CURRENT_TIMESTAMP`  |
| resolved      | BOOLEAN   | Indicates if resolved            |

### `untracked_serial_sales`
| Column        | Type      | Description                      |
|---------------|-----------|----------------------------------|
| id            | SERIAL    | Primary key                      |
| product_id    | INT       | FK to `products`                 |
| order_id      | TEXT      | Order reference                  |
| quantity      | INT       | Quantity sold without serials    |
| created_at    | TIMESTAMP | Defaults to `CURRENT_TIMESTAMP`  |

### `brands`
| Column        | Type    | Description                        |
|---------------|---------|------------------------------------|
| brand_id      | SERIAL  | Primary key                        |
| brand_name    | TEXT    | Unique brand name                  |

### `ssds`
| Column        | Type    | Description                        |
|---------------|---------|------------------------------------|
| ssd_id        | SERIAL  | Primary key                        |
| label         | TEXT    | Label for SSD type (e.g., 512GB)   |

### `users`
| Column        | Type    | Description                        |
|---------------|---------|------------------------------------|
| user_id       | SERIAL  | Primary key                        |
| username      | TEXT    | Unique login                       |
| password_hash | TEXT    | Hashed user password (never stored in plaintext) |
| is_admin      | BOOLEAN | Whether user has admin privileges  |

---

### 👁️ Views

- `view_master_sku_summary`: Aggregates master SKUs with product variant counts and total inventory units
- `view_product_stock_summary`: Supports frontend dashboard grouping
- `view_serials_with_part_numbers`: Lists inventory serials with part numbers and PO info
- `view_product_details_readable`: Joins products with brand and category for UI
- `view_monthly_inventory_summary`: Summarized monthly movement for reports
- `manual_review_log_view`: Matches serials against shipped items and flags missing data

---

## Screenshots (Previous Version)

These screenshots show an earlier build of the system. For the most up-to-date functionality, see the demo video above.

![Dashboard view](screenshots/DashboardBlur.png)
![Log view](screenshots/LogBlur.png)
![Review view](screenshots/ReviewBlur.png)
![Login view](screenshots/Login.png)
![ScanSerial view](screenshots/ScanSerial.PNG)
![AddDelivery view](screenshots/AddDelivery.PNG)
![AddSKU view](screenshots/AddSKU.PNG)

---

## Deployment Notes

> ⚠️ **Important:** You must create three `.env` files before running the system. These are excluded from version control for security. Never commit `.env` files containing secrets.

### 1. Backend `.env` file — `inventory_backend/.env`
```env
DATABASE_URL=postgresql://<your_username>:<your_password>@<your_host>:5432/<your_database>
VEEQO_API_KEY=<your_veeqo_api_key>
VITE_API_HOST=http://<your_backend_ip>:8000
```

### 2. Scanner `.env` file — `inventory_scanner/.env`
```env
API_BASE_URL=http://<your_backend_ip>:8000/scanner
```

### 3. Dashboard `.env` file — `inventory_dashboard/frontend/.env`
```env
VITE_API_HOST=http://<your_backend_ip>:8000
```

- The backend can be run as a Windows service using NSSM for persistent background execution.
- The desktop scanner app can be packaged as a portable `.exe` using PyInstaller — no Python install required.

---

## 🛠️ Running It Locally

### 1. Backend API (FastAPI)
```bash
cd inventory_backend
python -m venv env
env\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Frontend Dashboard (React)
```bash
cd inventory_dashboard/frontend
npm install
npm run dev
```

### 3. Desktop Scanner App (PyQt5)
```bash
cd inventory_scanner
start_main.bat
```
