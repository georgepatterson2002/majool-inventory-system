from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QMessageBox, QAbstractItemView, QTabWidget, QComboBox, QTableWidgetItem, QHeaderView
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import Qt, QUrl, QTimer
import requests
import os
from dotenv import load_dotenv
from app.api_client import fetch_master_skus, fetch_categories, fetch_brands
import sys


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL")

class InventoryView(QWidget):
    def __init__(self, user_id, is_admin=False):
        super().__init__()
        self.user_id = user_id
        self.setWindowTitle("Majool SN Scanner")
        self.setWindowIcon(QIcon("assets/icon.ico"))
        self.resize(900, 800)

        # --- Common Toggle Button ---
        self.toggle_button = QPushButton("Add Delivery")
        self.toggle_button.clicked.connect(self.toggle_mode)

        self.logout_button = QPushButton("Logout")
        self.logout_button.clicked.connect(self.handle_logout)

        # ------------------ SCAN MODE ------------------ #
        self.status_label = QLabel("Loading units...")
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.refresh_button = QPushButton("Refresh Table")
        self.refresh_button.clicked.connect(self.load_data)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Scan or type new serial number")
        self.serial_input.textChanged.connect(self.reset_input_timer)

        self.input_timer = QTimer()
        self.input_timer.setSingleShot(True)
        self.input_timer.timeout.connect(self.assign_serial)

        self.assign_button = QPushButton("Assign Serial to Selected Row")
        self.assign_button.clicked.connect(self.assign_serial)

        # Layout for scan mode
        self.scan_layout = QVBoxLayout()
        self.scan_layout.addWidget(self.status_label)
        self.scan_layout.addWidget(self.refresh_button)
        self.scan_layout.addWidget(self.table)
        self.scan_layout.addWidget(self.serial_input)
        self.scan_layout.addWidget(self.assign_button)

        self.scan_container = QWidget()
        self.scan_container.setLayout(self.scan_layout)

        self.error_sound = QSoundEffect()
        self.error_sound.setSource(QUrl.fromLocalFile(resource_path("assets/error.wav")))
        self.error_sound.setVolume(0.9)

        # ------------------ DELIVERY MODE ------------------ #
        self.tabs = QTabWidget()
        self.delivery_container = self.tabs  # reuse existing variable

        self.tab_delivery = QWidget()
        self.tab_product = QWidget()

        self.tabs.addTab(self.tab_delivery, "Add Delivery")

        if is_admin:
            self.tabs.addTab(self.tab_product, "Add SKU")

        self.tabs.hide()  # default to hidden

        # Tab layouts
        self.delivery_layout = QVBoxLayout()
        self.tab_delivery.setLayout(self.delivery_layout)

        self.product_layout = QVBoxLayout()
        self.tab_product.setLayout(self.product_layout)

        # --- Inputs for Add Product ---
        self.part_number_input = QLineEdit()
        self.part_number_input.setPlaceholderText("Part Number (SKU)")

        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("Product Name")

        self.brand_dropdown = QComboBox()
        self.brand_dropdown.addItem("Loading...", -1)

        self.master_sku_dropdown = QComboBox()
        self.master_sku_dropdown.addItem("Loading...", -1)

        self.category_dropdown = QComboBox()
        self.category_dropdown.addItem("Loading...", -1)

        self.product_submit_button = QPushButton("Add Product")
        self.product_submit_button.clicked.connect(self.submit_product)

        # Add to layout
        self.product_layout.addWidget(QLabel("Part Number (SKU):"))
        self.product_layout.addWidget(self.part_number_input)

        self.product_layout.addWidget(QLabel("Description:"))
        self.product_layout.addWidget(self.product_name_input)

        self.product_layout.addWidget(QLabel("Brand:"))
        self.product_layout.addWidget(self.brand_dropdown)

        self.product_layout.addWidget(QLabel("Master SKU:"))
        self.product_layout.addWidget(self.master_sku_dropdown)

        self.product_layout.addWidget(QLabel("Category:"))
        self.product_layout.addWidget(self.category_dropdown)

        self.product_layout.addWidget(self.product_submit_button)

        # ------------------ MAIN LAYOUT ------------------ #
        layout = QVBoxLayout()
        layout.addWidget(self.logout_button)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.scan_container)
        layout.addWidget(self.delivery_container)

        self.setLayout(layout)

        # Load initial scan table
        self.load_data()

    def handle_logout(self):
        from app.ui_main import MainWindow
        from app.state_manager import AppState

        AppState.logout()
        self.main_window = MainWindow()
        self.main_window.show()
        self.close()

    def load_data(self):
        try:
            response = requests.get(f"{API_BASE_URL}/noser-units")
            data = response.json()
            self.status_label.setText(f"{len(data)} items found")
            self.populate_table(data)
            self.select_first_valid_row()
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")

    def select_first_valid_row(self):
        for row in range(self.table.rowCount()):
            unit_id_item = self.table.item(row, 5)
            if unit_id_item and unit_id_item.text().isdigit():
                self.table.selectRow(row)
                break

    def reset_input_timer(self):
        self.input_timer.start(150)  # Wait 150ms after typing stops

    def populate_table(self, data):
        from app.api_client import fetch_brands

        headers = [
            "SKU", "Description", "Category", "MASTER SKU",
            "Brand", "Unit ID", "PO Number"
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(0)  # Clear any existing rows

        # Sort data by master_sku_id
        data.sort(key=lambda x: x["master_sku_id"])

        # 🧠 Create brand lookup map (ID → name)
        brand_lookup = {b["brand_id"]: b["brand_name"] for b in fetch_brands()}

        current_sku = None
        row_index = 0
        visible_row_number = 1  # For visible vertical numbering (excluding headers)

        for row in data:
            if row["master_sku_id"] != current_sku:
                # Insert a group header row
                self.table.insertRow(row_index)
                group_item = QTableWidgetItem(f"📦 Master SKU: {row['master_sku_id']} – {row['master_description']}")
                group_item.setBackground(Qt.lightGray)
                group_item.setFont(QFont("Arial", weight=QFont.Bold))
                group_item.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row_index, 0, group_item)
                self.table.setSpan(row_index, 0, 1, len(headers))

                # Hide vertical header number for group header
                self.table.setVerticalHeaderItem(row_index, QTableWidgetItem(""))

                row_index += 1
                current_sku = row["master_sku_id"]

            # Insert actual data row
            self.table.insertRow(row_index)
            values = [
                row["part_number"],
                row["master_description"],
                row["category"],
                row["master_sku_id"],
                brand_lookup.get(row["brand"], f"(Unknown ID: {row['brand']})"),
                row["unit_id"],
                row["po_number"]
            ]
            for col_idx, value in enumerate(values):
                self.table.setItem(row_index, col_idx, QTableWidgetItem(str(value)))

            # Number the row visibly (skip headers)
            self.table.setVerticalHeaderItem(row_index, QTableWidgetItem(str(visible_row_number)))
            visible_row_number += 1
            row_index += 1

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(self.table.NoEditTriggers)
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)

    def check_serial_input(self, text):
        text = text.strip()

        # Adjust this condition to fit your SN pattern
        if len(text) >= 4:  # e.g. SN must be at least 8 characters
            self.assign_serial()

    def assign_serial(self):
        selected = self.table.currentRow()

        if selected < 0:
            return  # No row selected, skip silently

        unit_id_item = self.table.item(selected, 5)

        if not unit_id_item or not unit_id_item.text().isdigit():
            return  # Invalid row (e.g., group header), skip silently

        unit_id = int(unit_id_item.text())
        new_serial = self.serial_input.text().strip()

        if not new_serial:
            return  # Ignore empty scan

        self.serial_input.clear()  # Clear immediately for next scan

        try:
            response = requests.post(f"{API_BASE_URL}/assign-serial", json={
                "unit_id": unit_id,
                "new_serial": new_serial,
                "user_id": self.user_id
            })

            if response.status_code == 200:
                self.load_data()
                self.serial_input.setFocus()
            else:
                try:
                    detail = response.json().get("detail", "Unknown error")
                except Exception:
                    detail = "Internal server error."

                self.error_sound.play()
                QMessageBox.critical(self, "Scan Error", f"Serial not assigned: {detail}")


        except Exception as e:
            QMessageBox.critical(self, "Error", f"Request failed: {str(e)}")

    def open_add_delivery_window(self):
        selected = self.product_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "No Selection", "Please select a product.")
            return

        product_id_item = self.product_table.item(selected, 5)
        if not product_id_item or not product_id_item.text().isdigit():
            QMessageBox.warning(self, "Invalid Row", "You must select a product row.")
            return

        product_id = int(product_id_item.text())

        from app.add_delivery_window import AddDeliveryWindow
        self.delivery_window = AddDeliveryWindow(self.user_id, self.load_data, default_product_id=product_id)
        self.delivery_window.show()

    def toggle_mode(self):
        if self.scan_container.isVisible():
            self.scan_container.hide()
            self.delivery_container.show()
            self.toggle_button.setText("Return to Scan Mode")
            self.load_product_table()
            self.load_product_form_dropdowns()
        else:
            self.delivery_container.hide()
            self.scan_container.show()
            self.toggle_button.setText("Add Delivery")

    def load_product_table(self):
        from app.api_client import fetch_product_list, add_delivery

        # Map brand_id → brand_name
        brand_lookup = {b["brand_id"]: b["brand_name"] for b in fetch_brands()}

        while self.delivery_layout.count():
            item = self.delivery_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Fetch product list
        products = fetch_product_list()
        if not products:
            self.delivery_layout.addWidget(QLabel("Failed to load products."))
            return

        # Table to show product list
        self.product_table = QTableWidget()
        self.product_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.product_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.product_table.setSelectionMode(QAbstractItemView.SingleSelection)

        headers = ["SKU", "Description", "Category", "MASTER SKU",
            "Brand", "Product ID"]
        self.product_table.setColumnCount(len(headers))
        self.product_table.setHorizontalHeaderLabels(headers)

        # Sort and group by master_sku_id
        products.sort(key=lambda p: p["master_sku_id"])
        row_index = 0
        current_msku = None

        for product in products:
            if product["master_sku_id"] != current_msku:
                # Group header
                self.product_table.insertRow(row_index)
                group_item = QTableWidgetItem(f"📦 {product['master_sku_id']} – {product['master_description']}")
                group_item.setBackground(Qt.lightGray)
                group_item.setFont(QFont("Arial", weight=QFont.Bold))
                group_item.setFlags(Qt.ItemIsEnabled)
                self.product_table.setItem(row_index, 0, group_item)
                self.product_table.setSpan(row_index, 0, 1, len(headers))
                row_index += 1
                current_msku = product["master_sku_id"]

            # Product row
            self.product_table.insertRow(row_index)
            row_data = [
                product["part_number"],
                product["master_description"],
                product["category"],
                product["master_sku_id"],
                brand_lookup.get(product["brand"], f"(Unknown ID: {product['brand']})"),
                product["product_id"]
            ]
            for col, value in enumerate(row_data):
                self.product_table.setItem(row_index, col, QTableWidgetItem(str(value)))
            row_index += 1

        self.product_table.resizeColumnsToContents()
        self.product_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.delivery_layout.addWidget(self.product_table)

        confirm_btn = QPushButton("Open Delivery Form")
        confirm_btn.clicked.connect(self.open_add_delivery_window)
        self.delivery_layout.addWidget(confirm_btn)
        

    def submit_delivery(self):
        selected = self.product_table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "No Selection", "Please select a product row.")
            return

        product_id_item = self.product_table.item(selected, 5)

        if not product_id_item or not product_id_item.text().isdigit():
            QMessageBox.warning(self, "Invalid Row", "You must select a product row, not a group header.")
            return

        product_id = int(product_id_item.text())
        quantity_str = self.qty_input.text().strip()

        if not quantity_str.isdigit() or int(quantity_str) <= 0:
            QMessageBox.warning(self, "Invalid Quantity", "Please enter a positive number.")
            return

        quantity = int(quantity_str)

        from app.api_client import add_delivery
        result = add_delivery(product_id, quantity, self.user_id)

        if result["success"]:
            QMessageBox.information(self, "Success", "Delivery added.")
            self.toggle_mode()  # Go back to scanner
            self.load_data()  # Refresh NOSER list
        else:
            QMessageBox.critical(self, "Error", f"Failed: {result['detail']}")

    def load_product_form_dropdowns(self):

        self.master_sku_dropdown.clear()
        self.category_dropdown.clear()
        self.brand_dropdown.clear()

        master_skus = fetch_master_skus()
        brands = fetch_brands()

        for brand in brands:
            self.brand_dropdown.addItem(brand["brand_name"], brand["brand_id"])

        for msku in master_skus:
            label = f"{msku['master_sku_id']} – {msku['description']}"
            self.master_sku_dropdown.addItem(label, msku["master_sku_id"])

        categories = fetch_categories()
        for cat in categories:
            self.category_dropdown.addItem(cat["name"], cat["category_id"])

    def submit_product(self):

        from app.api_client import add_product

        part_number = self.part_number_input.text().strip()
        product_name = self.product_name_input.text().strip()
        brand = self.brand_dropdown.currentData()
        master_sku_id = self.master_sku_dropdown.currentData()
        category_id = self.category_dropdown.currentData()

        if not part_number or not product_name or not brand:
            QMessageBox.warning(self, "Missing Fields", "Please fill in all fields.")
            return

        if master_sku_id is None or category_id is None:
            QMessageBox.warning(self, "Missing Info", "Please select a Master SKU and Category.")
            return

        result = add_product(part_number, product_name, brand, master_sku_id, category_id)

        if result["success"]:
            QMessageBox.information(self, "Success", "Product added.")
            self.toggle_mode()       # return to scanner
            self.load_data()         # refresh NOSER
        else:
            QMessageBox.critical(self, "Error", f"Failed: {result['detail']}")

