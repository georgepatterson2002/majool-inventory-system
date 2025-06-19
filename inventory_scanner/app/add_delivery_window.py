from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QMessageBox, QFormLayout
)
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import Qt
from app.api_client import fetch_product_list, add_delivery

class AddDeliveryForm(QWidget):
    def __init__(self, user_id, refresh_callback, default_product_id=None):
        super().__init__()
        self.refresh_callback = refresh_callback  # should expect go_to_scan param
        self.user_id = user_id
        self.refresh_callback = refresh_callback
        self.default_product_id = default_product_id

        # --- Inputs ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Scan or type SKU...")
        self.search_input.textChanged.connect(self.filter_products)

        self.product_dropdown = QComboBox()

        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("e.g. 5")
        self.qty_input.setValidator(QIntValidator(1, 10000))

        self.po_input = QLineEdit()
        self.po_input.setPlaceholderText("PO Number (not Order ID)")
        self.po_input.setMaxLength(30)

        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Optional (e.g. CN, SP)")
        self.prefix_input.setMaxLength(2)

        self.submit_button = QPushButton("Confirm Delivery")
        self.submit_button.clicked.connect(self.submit_delivery)

        # --- Layout ---
        layout = QFormLayout()
        layout.addRow("Search SKU:", self.search_input)
        layout.addRow("Select Product:", self.product_dropdown)
        layout.addRow("Quantity:", self.qty_input)
        layout.addRow("PO Number:", self.po_input)
        layout.addRow("SN Prefix (optional):", self.prefix_input)
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

        self.load_products()

    def load_products(self):
        products = fetch_product_list()
        self.full_product_list = products

        if not products:
            QMessageBox.critical(self, "Error", "Failed to load products.")
            return

        for idx, product in enumerate(products):
            label = f"{product['part_number']} – {product['product_name']} (ID {product['product_id']})"
            self.product_dropdown.addItem(label, product["product_id"])
            if self.default_product_id and product["product_id"] == self.default_product_id:
                self.product_dropdown.setCurrentIndex(idx)

    def submit_delivery(self):
        product_id = self.product_dropdown.currentData()
        quantity_str = self.qty_input.text().strip()
        po_number = self.po_input.text().strip()
        sn_prefix = self.prefix_input.text().strip().upper()

        if not quantity_str.isdigit() or int(quantity_str) <= 0:
            QMessageBox.warning(self, "Invalid Quantity", "Please enter a valid quantity.")
            return

        if not po_number or len(po_number) < 3:
            QMessageBox.warning(self, "Missing PO Number", "Please enter a valid PO number.")
            return

        if po_number.startswith("11-") or po_number.count("-") >= 2:
            QMessageBox.warning(self, "PO Number Format", "That looks like an Order ID. Please enter a PO Number.")
            return

        if sn_prefix and (len(sn_prefix) != 2 or not sn_prefix.isalnum()):
            QMessageBox.warning(self, "Invalid SN Prefix", "SN Prefix must be 2 alphanumeric characters.")
            return

        quantity = int(quantity_str)

        result = add_delivery(product_id, quantity, self.user_id, po_number, sn_prefix if sn_prefix else None)

        if result["success"]:
            QMessageBox.information(self, "Success", "Delivery added.")
            self.refresh_callback(go_to_scan=True)

            # Clear inputs for next entry
            self.qty_input.clear()
            self.po_input.clear()
            self.prefix_input.clear()
            self.search_input.clear()
            self.product_dropdown.setCurrentIndex(0)
            self.qty_input.setFocus()

        else:
            QMessageBox.critical(self, "Error", f"Failed to add delivery: {result['detail']}")

    def filter_products(self):
        text = self.search_input.text().strip().lower()

        if not text:
            filtered = self.full_product_list
        else:
            filtered = [
                p for p in self.full_product_list
                if text in p["part_number"].lower() or text in p["product_name"].lower()
            ]

        self.populate_dropdown(filtered)

    def populate_dropdown(self, product_list):
        self.product_dropdown.clear()
        if not product_list:
            self.product_dropdown.addItem("No matching products", -1)
            return

        selected_idx = 0
        for idx, product in enumerate(product_list):
            label = f"{product['part_number']} – {product['product_name']} (ID {product['product_id']})"
            self.product_dropdown.addItem(label, product["product_id"])
            if self.default_product_id and product["product_id"] == self.default_product_id:
                selected_idx = idx
        self.product_dropdown.setCurrentIndex(selected_idx)
