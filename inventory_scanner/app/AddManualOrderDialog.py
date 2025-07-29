from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QHBoxLayout, QPushButton, QMessageBox, QScrollArea, QWidget, QFormLayout
)
from PyQt5.QtCore import Qt
from app.api_client import create_manual_order  # We'll add this to api_client.py


class AddManualOrderDialog(QDialog):
    def __init__(self, full_product_list, parent=None):
        super().__init__(parent)
        self.full_product_list = full_product_list
        self.setWindowTitle("Add Manual Order")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Product selection
        layout.addWidget(QLabel("Search and select product:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search SKU or product name...")
        layout.addWidget(self.search_input)

        self.dropdown = QComboBox()
        layout.addWidget(self.dropdown)

        # Serial checkbox
        self.has_serials_checkbox = QCheckBox("I have serial numbers")
        layout.addWidget(self.has_serials_checkbox)
        self.has_serials_checkbox.stateChanged.connect(self.toggle_serials_mode)

        # Order ID (only visible if has_serials)
        self.order_id_input = QLineEdit()
        self.order_id_input.setPlaceholderText("Enter Order ID")
        self.order_id_input.setVisible(False)
        layout.addWidget(self.order_id_input)

        # Quantity
        layout.addWidget(QLabel("Quantity:"))
        self.quantity_input = QLineEdit()
        self.quantity_input.setPlaceholderText("Enter number of items")
        layout.addWidget(self.quantity_input)
        self.quantity_input.textChanged.connect(self.update_serial_inputs)

        # Serial fields container (scrollable)
        self.serials_container = QScrollArea()
        self.serials_container.setVisible(False)
        self.serials_widget = QWidget()
        self.serials_layout = QFormLayout(self.serials_widget)
        self.serials_container.setWidgetResizable(True)
        self.serials_container.setWidget(self.serials_widget)
        layout.addWidget(self.serials_container)

        # Buttons
        button_row = QHBoxLayout()
        confirm_btn = QPushButton("Submit")
        cancel_btn = QPushButton("Cancel")
        confirm_btn.clicked.connect(self.submit_order)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(confirm_btn)
        button_row.addWidget(cancel_btn)
        layout.addLayout(button_row)

        # Filter products on search
        self.search_input.textChanged.connect(self.filter_products)
        self.filter_products()

    def filter_products(self):
        text = self.search_input.text().strip().lower()
        filtered = self.full_product_list if not text else [
            p for p in self.full_product_list
            if text in p["part_number"].lower() or text in p["product_name"].lower()
        ]
        self.dropdown.clear()
        if not filtered:
            self.dropdown.addItem("No matching products", -1)
        else:
            for p in filtered:
                label = f"{p['part_number']} – {p['product_name']} (ID {p['product_id']})"
                self.dropdown.addItem(label, p["product_id"])

    def toggle_serials_mode(self):
        has_serials = self.has_serials_checkbox.isChecked()
        self.order_id_input.setVisible(has_serials)
        self.serials_container.setVisible(has_serials)
        self.update_serial_inputs()

    def update_serial_inputs(self):
        # Clear existing serial inputs
        for i in reversed(range(self.serials_layout.count())):
            item = self.serials_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        if not self.has_serials_checkbox.isChecked():
            return

        try:
            qty = int(self.quantity_input.text())
        except ValueError:
            qty = 0

        # 🔹 Cap the quantity to prevent UI crash
        MAX_ITEMS = 20
        if qty > MAX_ITEMS:
            QMessageBox.warning(self, "Quantity Limit",
                                f"Maximum allowed items is {MAX_ITEMS}.")
            self.quantity_input.setText(str(MAX_ITEMS))
            qty = MAX_ITEMS

        for i in range(qty):
            line = QLineEdit()
            line.setPlaceholderText(f"Enter serial number for item #{i+1}")
            self.serials_layout.addRow(QLabel(f"Item #{i+1}:"), line)

    def submit_order(self):
        product_id = self.dropdown.currentData()
        if product_id == -1 or not product_id:
            QMessageBox.warning(self, "Missing Product", "Please select a valid product.")
            return

        try:
            quantity = int(self.quantity_input.text())
            if quantity <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid Quantity", "Enter a valid quantity.")
            return

        has_serials = self.has_serials_checkbox.isChecked()

        if has_serials:
            order_id = self.order_id_input.text().strip()
            if not order_id:
                QMessageBox.warning(self, "Missing Order ID", "Please enter an Order ID.")
                return

            # Collect serials
            serials = []
            for i in range(self.serials_layout.count()):
                field = self.serials_layout.itemAt(i, QFormLayout.FieldRole).widget()
                val = field.text().strip()
                if not val:
                    QMessageBox.warning(self, "Missing Serial", f"Serial for item #{i+1} is empty.")
                    return
                serials.append(val)

            if len(serials) != quantity:
                QMessageBox.warning(self, "Mismatch", "Number of serials must match quantity.")
                return

            payload = {
                "product_id": product_id,
                "order_id": order_id,
                "quantity": quantity,
                "serials": serials
            }

        else:
            payload = {
                "product_id": product_id,
                "quantity": quantity
            }

        # Send to backend
        try:
            create_manual_order(payload)
            QMessageBox.information(self, "Success", "Manual order added successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
