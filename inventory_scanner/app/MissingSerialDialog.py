# MissingSerialDialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QMessageBox, QFormLayout
)
from PyQt5.QtGui import QIntValidator
from app.api_client import fetch_product_list

class MissingSerialDialog(QDialog):
    def __init__(self, order_id, quantity, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Product")

        self.order_id = order_id
        self.quantity = quantity
        self.selected_product_id = None

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type SKU or name...")
        self.search_input.textChanged.connect(self.filter_products)

        self.product_dropdown = QComboBox()

        self.layout = QFormLayout()
        self.layout.addRow("Search:", self.search_input)
        self.layout.addRow("Select Product:", self.product_dropdown)

        self.submit_btn = QPushButton("Confirm")
        self.submit_btn.clicked.connect(self.accept_selection)
        self.layout.addRow(self.submit_btn)

        self.setLayout(self.layout)
        self.load_products()


    def load_products(self):
        self.full_product_list = fetch_product_list()
        self.populate_dropdown(self.full_product_list)

    def filter_products(self):
        text = self.search_input.text().strip().lower()
        filtered = [
            p for p in self.full_product_list
            if text in p["part_number"].lower() or text in p["product_name"].lower()
        ]
        self.populate_dropdown(filtered)

    def populate_dropdown(self, products):
        self.product_dropdown.clear()
        for p in products:
            label = f"{p['part_number']} – {p['product_name']} (ID {p['product_id']})"
            self.product_dropdown.addItem(label, p["product_id"])

    def accept_selection(self):
        self.selected_product_id = self.product_dropdown.currentData()
        if self.selected_product_id is None or self.selected_product_id == -1:
            QMessageBox.warning(self, "Error", "Please select a valid product from the dropdown.")
            return
        self.accept()