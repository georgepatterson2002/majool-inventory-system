from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QLineEdit, QMessageBox
)
from app.api_client import fetch_product_list, add_delivery

class AddDeliveryWindow(QWidget):
    def __init__(self, user_id, refresh_callback):
        super().__init__()
        self.setWindowTitle("Add Delivery")
        self.setFixedSize(400, 200)
        self.user_id = user_id
        self.refresh_callback = refresh_callback

        self.label = QLabel("Select Product by SKU:")
        self.product_dropdown = QComboBox()

        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("Enter quantity (e.g. 5)")

        self.submit_button = QPushButton("Confirm Delivery")
        self.submit_button.clicked.connect(self.submit_delivery)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.product_dropdown)
        layout.addWidget(self.qty_input)
        layout.addWidget(self.submit_button)
        self.setLayout(layout)

        self.load_products()

    def load_products(self):
        products = fetch_product_list()
        if not products:
            QMessageBox.critical(self, "Error", "Failed to load products.")
            self.close()
            return

        for product in products:
            display = f"{product['part_number']} – {product['product_name']} ({product['brand']})"
            self.product_dropdown.addItem(display, product["product_id"])

    def submit_delivery(self):
        product_id = self.product_dropdown.currentData()
        quantity_str = self.qty_input.text().strip()

        if not quantity_str.isdigit() or int(quantity_str) <= 0:
            QMessageBox.warning(self, "Invalid Quantity", "Please enter a valid quantity.")
            return

        quantity = int(quantity_str)
        result = add_delivery(product_id, quantity, self.user_id)

        if result["success"]:
            QMessageBox.information(self, "Success", "Delivery added.")
            self.refresh_callback()
            self.close()
        else:
            QMessageBox.critical(self, "Error", f"Failed to add delivery: {result['detail']}")
