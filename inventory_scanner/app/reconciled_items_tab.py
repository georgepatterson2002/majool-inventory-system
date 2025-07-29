from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QComboBox, QLabel, QHBoxLayout,
    QMessageBox, QDialog, QHeaderView
)
from PyQt5.QtCore import Qt
import requests
import os

API_BASE_URL = os.getenv("API_BASE_URL")

class ReconciledItemsTab(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

       
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Serial Number", "Part Number", "Memo Number", "Reconciled At"])
        self.layout.addWidget(QLabel("Reconciled Items"))
        self.layout.addWidget(self.table)

        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)

        self.full_product_list = self.fetch_products()
        self.load_data()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.add_button = QPushButton("Add New")
        self.add_button.clicked.connect(self.open_add_dialog)
        btn_layout.addWidget(self.add_button)

        self.resolve_button = QPushButton("Resolve Selected")
        self.resolve_button.setEnabled(False)
        self.resolve_button.clicked.connect(self.resolve_selected)
        btn_layout.addWidget(self.resolve_button)

        self.table.itemSelectionChanged.connect(
            lambda: self.resolve_button.setEnabled(self.table.currentRow() >= 0)
        )

        self.layout.addLayout(btn_layout)

    def fetch_products(self):
        try:
            response = requests.get(f"{API_BASE_URL}/products")
            return response.json()
        except:
            return []

    def load_data(self):
        self.table.setRowCount(0)
        try:
            from app.api_client import fetch_reconciled_items
            items = fetch_reconciled_items()

            if not isinstance(items, list):
                raise ValueError("Expected list of reconciled items")

            for i, item in enumerate(items):
                self.table.insertRow(i)
                sn_item = QTableWidgetItem(item.get("serial_number", ""))
                sn_item.setData(Qt.UserRole, item.get("reconciled_id"))  # Store ID for resolve
                self.table.setItem(i, 0, sn_item)
                self.table.setItem(i, 1, QTableWidgetItem(item.get("part_number", "")))
                self.table.setItem(i, 2, QTableWidgetItem(item.get("memo_number", "")))
                self.table.setItem(i, 3, QTableWidgetItem(item.get("reconciled_at", "")))
        except Exception as e:
            print(f"Failed to load reconciled items: {str(e)}")

    def open_add_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Reconciled Item")
        dialog.resize(400, 240)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Add Manually by Part Number"))

        # Part number search
        part_search = QLineEdit()
        part_search.setPlaceholderText("Search part number")
        layout.addWidget(part_search)

        part_dropdown = QComboBox()
        layout.addWidget(part_dropdown)

        serial_input = QLineEdit()
        serial_input.setPlaceholderText("Serial number")
        layout.addWidget(serial_input)

        memo_input = QLineEdit()
        memo_input.setPlaceholderText("Memo number")
        layout.addWidget(memo_input)

        add_btn = QPushButton("Add Reconciled Item")
        layout.addWidget(add_btn)

        # Populate dropdown
        def filter_parts():
            query = part_search.text().lower().strip()
            part_dropdown.clear()
            for p in self.full_product_list:
                if query in p["part_number"].lower() or query in p["product_name"].lower():
                    part_dropdown.addItem(f"{p['part_number']} – {p['product_name']}", p["product_id"])

        part_search.textChanged.connect(filter_parts)
        filter_parts()

        def submit():
            product_id = part_dropdown.currentData()
            serial = serial_input.text().strip()
            memo = memo_input.text().strip()

            if not product_id or not serial or not memo:
                QMessageBox.warning(dialog, "Missing Fields", "All fields are required.")
                return

            # Step 1: mark unit as sold if exists
            try:
                response = requests.post(
                    f"{API_BASE_URL}/fix-serial-status",
                    json={"serial_number": serial}
                )

                if response.status_code == 404:
                    # Serial not found, but continue and inform the user
                    QMessageBox.information(dialog, "Notice", f"Serial '{serial}' was not found in inventory. Item will still be reconciled.")
                elif response.status_code != 200:
                    # Any other error – show warning but still allow reconcile attempt
                    QMessageBox.warning(dialog, "Warning", f"Could not mark serial as sold:\n{response.text}")
            except Exception as e:
                QMessageBox.warning(dialog, "Network Error", str(e))

            # Step 2: insert into reconciled_items
            try:
                from app.api_client import add_reconciled_item
                result = add_reconciled_item(product_id, serial, memo)
                if result.get("success"):
                    self.load_data()
                    dialog.accept()
                else:
                    # Show as warning instead of critical so it doesn't block the workflow
                    QMessageBox.warning(dialog, "Reconcile Issue", result.get("detail", "Item added, but with warnings."))
                    self.load_data()
                    dialog.accept()
            except Exception as e:
                QMessageBox.critical(dialog, "Request Error", str(e))

        add_btn.clicked.connect(submit)
        dialog.exec_()



    def resolve_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return

        item = self.table.item(row, 0)
        if not item:
            return

        # Get reconciled_id from hidden Qt.UserRole
        reconciled_id = self.table.item(row, 0).data(Qt.UserRole)
        if not reconciled_id:
            QMessageBox.warning(self, "Missing Data", "Could not find ID for selected row.")
            return

        confirm = QMessageBox.question(self, "Confirm Resolve", "Mark this item as resolved?")
        if confirm != QMessageBox.Yes:
            return

        from app.api_client import resolve_reconciled_item
        result = resolve_reconciled_item(reconciled_id)
        if result.get("success"):
            self.load_data()
        else:
            QMessageBox.warning(self, "Failed", result.get("detail", "Unknown error"))
