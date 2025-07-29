# app/damaged_items_tab.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QHeaderView, QMessageBox,
    QLabel, QLineEdit, QComboBox, QDialog
)
from PyQt5.QtCore import Qt
import requests
import os
from app.api_client import fetch_product_list

API_BASE_URL = os.getenv("API_BASE_URL")


class DamagedItemsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["SKU", "Serial Number", "Product Name"])
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)

        button_layout = QHBoxLayout()

        self.add_damaged_btn = QPushButton("Add Damaged Unit")
        self.add_damaged_btn.clicked.connect(self.open_add_damaged_dialog)
        button_layout.addWidget(self.add_damaged_btn)
        
        self.repair_btn = QPushButton("Mark as Repaired")
        self.dispose_btn = QPushButton("Dispose")
        self.repair_btn.setEnabled(False)
        self.dispose_btn.setEnabled(False)
        button_layout.addWidget(self.repair_btn)
        button_layout.addWidget(self.dispose_btn)
        self.layout.addLayout(button_layout)

        self.repair_btn.clicked.connect(self.mark_repaired)
        self.dispose_btn.clicked.connect(self.mark_disposed)

        self.table.itemSelectionChanged.connect(self.update_button_state)

        self.full_product_list = fetch_product_list()
        self.load_damaged_units()

    def update_button_state(self):
        selected = self.table.currentRow() >= 0
        self.repair_btn.setEnabled(selected)
        self.dispose_btn.setEnabled(selected)

    def load_damaged_units(self):
        self.table.setRowCount(0)
        try:
            response = requests.get(f"{API_BASE_URL}/damaged-units")
            if response.status_code != 200:
                raise ValueError(response.text)

            units = response.json()
            if not isinstance(units, list):
                raise ValueError("Expected list of damaged units")

            for i, unit in enumerate(units):
                self.table.insertRow(i)
                sku_item = QTableWidgetItem(unit.get("part_number", ""))
                sku_item.setData(Qt.UserRole, unit.get("unit_id"))
                self.table.setItem(i, 0, sku_item)
                self.table.setItem(i, 1, QTableWidgetItem(unit.get("serial_number", "")))
                self.table.setItem(i, 2, QTableWidgetItem(unit.get("product_name", "")))

        except Exception as e:
            print(f"Failed to load damaged units: {str(e)}")

    def get_selected_unit(self):
        row = self.table.currentRow()
        if row < 0:
            return None, None

        sku_item = self.table.item(row, 0)
        unit_id = sku_item.data(Qt.UserRole)
        part_number = sku_item.text()

        product_id = None
        for p in self.full_product_list:
            if p["part_number"] == part_number:
                product_id = p["product_id"]
                break

        return unit_id, product_id

    def mark_repaired(self):
        unit_id, _ = self.get_selected_unit()
        if not unit_id:
            return

        # Inline dialog for optional SKU selection
        dialog = QDialog(self)
        dialog.setWindowTitle("Mark as Repaired")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        label = QLabel("Optionally select a new SKU if the product was upgraded or changed:")
        layout.addWidget(label)

        search_input = QLineEdit()
        search_input.setPlaceholderText("Search SKU or product name...")
        layout.addWidget(search_input)

        dropdown = QComboBox()
        layout.addWidget(dropdown)

        note = QLabel("If the SKU is not shown, please add it first using the Add SKU tab.")
        note.setStyleSheet("color: #a00; font-style: italic;")
        layout.addWidget(note)

        def filter_products():
            text = search_input.text().strip().lower()
            filtered = self.full_product_list if not text else [
                p for p in self.full_product_list
                if text in p["part_number"].lower() or text in p["product_name"].lower()
            ]
            dropdown.clear()
            if not filtered:
                dropdown.addItem("No matching products", -1)
            else:
                for p in filtered:
                    label = f"{p['part_number']} – {p['product_name']} (ID {p['product_id']})"
                    dropdown.addItem(label, p["product_id"])

        search_input.textChanged.connect(filter_products)
        filter_products()

        # Confirm/cancel buttons
        button_row = QHBoxLayout()
        confirm_btn = QPushButton("Confirm")
        cancel_btn = QPushButton("Cancel")
        confirm_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        button_row.addWidget(confirm_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        if dialog.exec_() != QDialog.Accepted:
            return  # Cancelled

        new_product_id = dropdown.currentData()
        if new_product_id == -1:
            new_product_id = None

        payload = {"unit_id": unit_id}
        if new_product_id:
            payload["new_product_id"] = new_product_id

        try:
            response = requests.post(f"{API_BASE_URL}/mark-repaired", json=payload)
            if response.status_code == 200:
                self.load_damaged_units()
            else:
                QMessageBox.warning(self, "Error", response.json().get("detail", "Unknown error"))
        except Exception as e:
            QMessageBox.critical(self, "Request Failed", str(e))

    def mark_disposed(self):
        unit_id, product_id = self.get_selected_unit()
        if not unit_id or not product_id:
            QMessageBox.warning(self, "Missing Info", "Could not find required unit or product ID.")
            return

        # 🔹 Confirm popup
        row = self.table.currentRow()
        sku = self.table.item(row, 0).text() if row >= 0 else ""
        serial = self.table.item(row, 1).text() if row >= 0 else ""

        confirm = QMessageBox.question(
            self,
            "Confirm Disposal",
            f"Dispose unit {serial} ({sku})?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return  # User cancelled

        try:
            response = requests.post(f"{API_BASE_URL}/dispose-unit", json={
                "unit_id": unit_id,
                "original_product_id": product_id
            })
            if response.status_code == 200:
                self.load_damaged_units()
            else:
                QMessageBox.warning(self, "Error", response.json().get("detail", "Unknown error"))
        except Exception as e:
            QMessageBox.critical(self, "Request Failed", str(e))

    def open_add_damaged_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Mark Existing Unit as Damaged")
        dialog.resize(400, 120)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Enter serial number of an already scanned unit:"))

        serial_input = QLineEdit()
        serial_input.setPlaceholderText("Serial number")
        layout.addWidget(serial_input)

        button_row = QHBoxLayout()
        confirm_btn = QPushButton("Mark Damaged")
        cancel_btn = QPushButton("Cancel")
        button_row.addWidget(confirm_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        confirm_btn.clicked.connect(lambda: self.submit_damaged(serial_input.text().strip(), dialog))
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec_()

    def submit_damaged(self, serial_number, dialog):
        if not serial_number:
            QMessageBox.warning(self, "Missing Serial", "Please enter a serial number.")
            return

        try:
            response = requests.post(
                f"{API_BASE_URL}/mark-damaged",
                json={"serial_number": serial_number}
            )
            if response.status_code == 200:
                self.load_damaged_units()
                dialog.accept()
            else:
                QMessageBox.warning(self, "Failed", response.json().get("detail", "Unknown error"))
        except Exception as e:
            QMessageBox.critical(self, "Request Error", str(e))
