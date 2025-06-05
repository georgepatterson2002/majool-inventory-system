from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QMessageBox, QFormLayout
)
from PyQt5.QtGui import QIntValidator
from PyQt5.QtCore import Qt
from app.api_client import fetch_product_list, add_delivery

class AddDeliveryWindow(QWidget):
    def __init__(self, user_id, refresh_callback, default_product_id=None):
        super().__init__()
        self.setWindowTitle("Add Delivery")
        self.setFixedSize(400, 250)
        self.user_id = user_id
        self.refresh_callback = refresh_callback
        self.default_product_id = default_product_id

        self.product_dropdown = QComboBox()
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("e.g. 5")
        self.qty_input.setValidator(QIntValidator(1, 10000))

        self.po_input = QLineEdit()
        self.po_input.setPlaceholderText("PO Number (not Order ID)")
        self.po_input.setMaxLength(30)

        self.submit_button = QPushButton("Confirm Delivery")
        self.submit_button.clicked.connect(self.submit_delivery)

        layout = QFormLayout()
        layout.addRow("Select Product:", self.product_dropdown)
        layout.addRow("Quantity:", self.qty_input)
        layout.addRow("PO Number:", self.po_input)
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

        self.load_products()

    def load_products(self):
        products = fetch_product_list()
        if not products:
            QMessageBox.critical(self, "Error", "Failed to load products.")
            self.close()
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

        if not quantity_str.isdigit() or int(quantity_str) <= 0:
            QMessageBox.warning(self, "Invalid Quantity", "Please enter a valid quantity.")
            return

        if not po_number or len(po_number) < 3:
            QMessageBox.warning(self, "Missing PO Number", "Please enter a valid PO number.")
            return

        # Prevent user from entering an Order ID like "111-1234567-1234567"
        if po_number.startswith("11-") or po_number.count("-") >= 2:
            QMessageBox.warning(self, "PO Number Format", "That looks like an Order ID. Please enter a PO Number.")
            return

        quantity = int(quantity_str)

        result = add_delivery(product_id, quantity, self.user_id, po_number)

        if result["success"]:
            QMessageBox.information(self, "Success", "Delivery added.")
            self.refresh_callback()
            self.close()
        else:
            QMessageBox.critical(self, "Error", f"Failed to add delivery: {result['detail']}")
