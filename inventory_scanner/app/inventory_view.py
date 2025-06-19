from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QMessageBox, QAbstractItemView, QTabWidget, QComboBox, QTableWidgetItem, QHeaderView, QDialog, QInputDialog, QFormLayout, QCheckBox
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import Qt, QUrl, QTimer
import requests
import os
from dotenv import load_dotenv
from app.api_client import fetch_master_skus, fetch_categories, fetch_brands, fetch_manual_reviews, resolve_manual_review, create_master_sku
from app.create_user_window import CreateUserForm
import sys


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

load_dotenv()

def show_strict_error_dialog(parent, serial_number, detail):
        parent.error_sound.play()

        dialog = QDialog(parent)
        dialog.setWindowTitle("Scan Error")
        dialog.setModal(True)
        dialog.setWindowModality(Qt.ApplicationModal)

        layout = QVBoxLayout()
        label = QLabel(f"Serial '{serial_number}' caused an error:\n\n{detail}")
        layout.addWidget(label)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        ok_button.setFocusPolicy(Qt.NoFocus)  # Prevent keyboard from activating this
        layout.addWidget(ok_button)

        dialog.setLayout(layout)

        # Block Enter, Return, and Escape keys from dismissing the dialog
        def block_keys(event):
            if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape):
                event.accept()  # ← This actively blocks the key press
                return
            super(QDialog, dialog).keyPressEvent(event)

        dialog.keyPressEvent = block_keys

        dialog.exec_()

API_BASE_URL = os.getenv("API_BASE_URL")

class InventoryView(QWidget):
    def __init__(self, user_id, is_admin=False):
        super().__init__()

        self.initialized = False

        self.user_id = user_id
        self.setWindowTitle("Majool SN Scanner")
        self.setWindowIcon(QIcon("assets/icon.ico"))
        self.resize(900, 800)

        # --- Common Toggle Button ---
        self.toggle_button = QPushButton("More Tools")
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
        self.serial_input.textChanged.connect(self.reset_input_timer)
        self.serial_input.setPlaceholderText("Scan new serial number")
        self.table.itemSelectionChanged.connect(self.focus_serial_input)

        

        self.assign_button = QPushButton("Assign Serial to Selected Row")
        self.assign_button.clicked.connect(self.assign_serial)

        # Layout for scan mode
        self.scan_layout = QVBoxLayout()
        self.scan_layout.addWidget(self.status_label)
        self.scan_layout.addWidget(self.refresh_button)
        self.scan_layout.addWidget(self.table)
        self.scan_layout.addWidget(self.serial_input)
        self.scan_layout.addWidget(self.assign_button)
        self.manual_entry_checkbox = QCheckBox("Manually enter serial number")
        self.manual_entry_checkbox.stateChanged.connect(self.toggle_manual_mode)
        self.scan_layout.addWidget(self.manual_entry_checkbox)

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
        self.tab_manual_review = QWidget()
        self.tab_create_user = QWidget()

        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.tabs.addTab(self.tab_delivery, "Add Delivery")

        if is_admin:
            self.tabs.addTab(self.tab_product, "Add SKU")
            self.tabs.addTab(self.tab_manual_review, "Manual Review")
            self.tabs.addTab(self.tab_create_user, "Create User")

        self.tabs.hide()  # default to hidden

        # Tab layouts
        self.delivery_layout = QVBoxLayout()
        self.tab_delivery.setLayout(self.delivery_layout)

        self.load_add_delivery_form()

        self.product_layout = QFormLayout()
        self.tab_product.setLayout(self.product_layout)

        self.manual_review_layout = QVBoxLayout()
        self.tab_manual_review.setLayout(self.manual_review_layout)

        self.create_user_layout = QVBoxLayout()
        self.tab_create_user.setLayout(self.create_user_layout)

        self.user_form = CreateUserForm(admin_user_id=self.user_id)
        self.create_user_layout.addWidget(self.user_form)

        # Placeholder message for now
        self.manual_review_layout.addWidget(QLabel("Manual Review Table Coming Soon..."))

        # --- Inputs for Add Product ---
        self.part_number_input = QLineEdit()
        self.part_number_input.setPlaceholderText("Part Number (SKU)")

        self.product_name_input = QLineEdit()
        self.product_name_input.setPlaceholderText("Product Name")

        self.brand_dropdown = QComboBox()
        self.brand_dropdown.addItem("Loading...", -1)

        self.master_sku_search = QLineEdit()
        self.master_sku_search.setPlaceholderText("Search Master SKU...")
        self.master_sku_search.textChanged.connect(self.filter_master_skus)

        self.master_sku_dropdown = QComboBox()
        self.master_sku_dropdown.addItem("Loading...", -1)

        self.category_dropdown = QComboBox()
        self.category_dropdown.addItem("Loading...", -1)

        self.product_submit_button = QPushButton("Add Product")
        self.product_submit_button.clicked.connect(self.submit_product)

        # Add to layout
        self.product_layout.addRow("Part Number (SKU):", self.part_number_input)
        self.product_layout.addRow("Description:", self.product_name_input)
        #self.product_layout.addRow("Brand:", self.brand_dropdown)
        self.product_layout.addRow("Search Master SKU:", self.master_sku_search)
        self.product_layout.addRow("Master SKU:", self.master_sku_dropdown)
        #self.product_layout.addRow("Category:", self.category_dropdown)
        self.product_layout.addRow(self.product_submit_button)


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
        self.serial_input.setFocus()

        self.input_timer = QTimer()
        self.input_timer.setSingleShot(True)
        self.input_timer.timeout.connect(self.assign_serial)

        

        # Load initial scan table
        self.load_data()
        self.serial_input.setFocus()

        # Initialize Add SKU dropdowns so MSKU search works
        self.load_product_form_dropdowns()


        self.initialized = True

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
            self.focus_serial_input()
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")

    def select_first_valid_row(self):
        for row in range(self.table.rowCount()):
            unit_id_item = self.table.item(row, 3)
            if unit_id_item and unit_id_item.text().isdigit():
                self.table.selectRow(row)
                break

    def focus_serial_input(self):
        self.serial_input.setFocus()
    
    # Wait 50ms after typing stops

    def populate_table(self, data):
        from app.api_client import fetch_brands

        headers = [
            "SKU", "Description", "MASTER SKU",
            "Unit ID", "PO Number"
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
                row["master_sku_id"],
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
        if self.manual_entry_checkbox.isChecked():
            return  # Do nothing in manual mode
        text = text.strip()
        if len(text) > 4:
            self.assign_serial()

    def assign_serial(self):
        selected = self.table.currentRow()
        if selected < 0:
            self.focus_serial_input()
            return

        unit_id_item = self.table.item(selected, 3)  # Column index for 'Unit ID' in v1.5
        if not unit_id_item or not unit_id_item.text().isdigit():
            self.focus_serial_input()
            return

        unit_id = int(unit_id_item.text())
        new_serial = self.serial_input.text().strip()

        if not new_serial or len(new_serial) <= 4:
            self.focus_serial_input()
            return

        try:
            response = requests.post(f"{API_BASE_URL}/assign-serial", json={
                "unit_id": unit_id,
                "new_serial": new_serial,
                "user_id": self.user_id
            })

            if response.status_code == 200:
                self.serial_input.clear()
                self.load_data()
                self.select_first_valid_row()
                self.focus_serial_input()
                return

            else:
                try:
                    detail = response.json().get("detail", "Unknown error")
                except Exception:
                    detail = "Internal server error"

                # Special handling for duplicate
                if "Serial number already exists" in detail:
                    confirm = QMessageBox.question(
                        self,
                        "Duplicate Serial Detected",
                        f"Serial '{new_serial}' already exists and may have been sold.\n\nWould you like to process this as a return?",
                        QMessageBox.Yes | QMessageBox.No
                    )

                    if confirm == QMessageBox.Yes:
                        try:
                            return_response = requests.post(f"{API_BASE_URL}/handle-return-scan", json={
                                "scanned_serial": new_serial,
                                "placeholder_unit_id": unit_id,
                                "user_id": self.user_id
                            })

                            if return_response.status_code == 200:
                                QMessageBox.information(self, "Return Complete", f"Serial {new_serial} was marked as returned.")
                                self.serial_input.clear()
                                self.load_data()
                                self.select_first_valid_row()
                                self.focus_serial_input()
                                return
                            else:
                                msg = return_response.json().get("detail", "Unknown error")
                                QMessageBox.critical(self, "Return Failed", f"Failed to process return:\n\n{msg}")
                        except Exception as e:
                            QMessageBox.critical(self, "Request Error", f"Error contacting server:\n{str(e)}")
                    else:
                        self.error_sound.play()
                        show_strict_error_dialog(self, new_serial, detail)
                else:
                    self.error_sound.play()
                    show_strict_error_dialog(self, new_serial, detail)

        except Exception as e:
            self.error_sound.play()
            show_strict_error_dialog(self, new_serial, f"Request failed: {str(e)}")

        self.serial_input.clear()
        self.select_first_valid_row()
        self.focus_serial_input()



    def toggle_mode(self):
        if self.scan_container.isVisible():
            self.scan_container.hide()
            self.delivery_container.show()
            self.toggle_button.setText("Return to Scan Mode")
        else:
            self.delivery_container.hide()
            self.scan_container.show()
            self.toggle_button.setText("More Tools")
            QTimer.singleShot(50, self.serial_input.setFocus) 

    def load_add_delivery_form(self):
        from app.add_delivery_window import AddDeliveryForm

        # Clean old widgets
        while self.delivery_layout.count():
            item = self.delivery_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Add new form
        self.delivery_form = AddDeliveryForm(self.user_id, self.handle_delivery_submitted)
        self.delivery_layout.addWidget(self.delivery_form)
    
    def handle_delivery_submitted(self, go_to_scan=False):
        self.load_data()
        if go_to_scan:
            self.toggle_mode()
        

    def load_product_form_dropdowns(self):

        self.full_master_sku_list = fetch_master_skus()

        self.master_sku_dropdown.clear()
        self.category_dropdown.clear()
        self.brand_dropdown.clear()

        master_skus = fetch_master_skus()
        brands = fetch_brands()

        for brand in brands:
            self.brand_dropdown.addItem(brand["brand_name"], brand["brand_id"])

        for msku in self.full_master_sku_list:
            label = f"{msku['master_sku_id']} – {msku['description']}"
            self.master_sku_dropdown.addItem(label, msku["master_sku_id"])

        categories = fetch_categories()
        default_index = 0

        for i, cat in enumerate(categories):
            self.category_dropdown.addItem(cat["name"], cat["category_id"])
            if cat["category_id"] == 2:
                default_index = i

        self.category_dropdown.setCurrentIndex(default_index)
   
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
        
        if master_sku_id == "DOESNOTEXIST":  # DOESNOTEXIST ID
            part_number = self.part_number_input.text().strip()
            product_name = self.product_name_input.text().strip()
            suggested_msku = f"MSKU-{part_number}"

            confirm = QMessageBox.question(
                self,
                "Create New Master SKU?",
                f"Master SKU doesn't exist.\nCreate one named '{suggested_msku}'?",
                QMessageBox.Yes | QMessageBox.No
            )

            if confirm == QMessageBox.Yes:
                # Check if it already exists
                existing_ids = [msku["master_sku_id"] for msku in self.full_master_sku_list]
                if suggested_msku in existing_ids:
                    QMessageBox.warning(self, "Already Exists", f"A Master SKU called '{suggested_msku}' already exists.")
                    return

                # Insert new MSKU
                from app.api_client import create_master_sku
                create_result = create_master_sku(suggested_msku, product_name)
                if not create_result.get("success"):
                    QMessageBox.critical(self, "MSKU Creation Failed", create_result.get("detail", "Unknown error"))
                    return

                master_sku_id = suggested_msku  # Use the new MSKU going forward


        result = add_product(part_number, product_name, brand, master_sku_id, category_id)

        if result["success"]:
            QMessageBox.information(self, "Success", "Product added.")
            self.load_data()         # Optionally refresh NOSER but stay on the Add SKU tab
        else:
            QMessageBox.critical(self, "Error", f"Failed: {result['detail']}")

    def load_manual_review_table(self):

        # Clear the layout
        while self.manual_review_layout.count():
            child = self.manual_review_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.review_table = QTableWidget()
        self.review_table.setColumnCount(3)
        self.review_table.setHorizontalHeaderLabels(["Order ID", "SKU", "Created At"])
        self.review_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.review_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.review_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.review_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        reviews = fetch_manual_reviews()
        self.review_table.setRowCount(len(reviews))

        for row_idx, item in enumerate(reviews):
            self.review_table.setItem(row_idx, 0, QTableWidgetItem(item["order_id"]))
            self.review_table.setItem(row_idx, 1, QTableWidgetItem(item["sku"]))
            self.review_table.setItem(row_idx, 2, QTableWidgetItem(item["created_at"]))

        self.manual_review_layout.addWidget(self.review_table)

        # Refresh button
        refresh_btn = QPushButton("Refresh Manual Review Table")
        refresh_btn.clicked.connect(self.load_manual_review_table)
        self.manual_review_layout.addWidget(refresh_btn)

        self.fix_btn = QPushButton("Veeqo Missed-Scan Fix")
        self.fix_btn.setEnabled(False)
        self.fix_btn.clicked.connect(self.fix_missed_scan)
        self.manual_review_layout.addWidget(self.fix_btn)

        self.review_table.itemSelectionChanged.connect(
            lambda: [
                self.resolve_btn.setEnabled(self.review_table.currentRow() >= 0),
                self.fix_btn.setEnabled(self.review_table.currentRow() >= 0)
            ]
        )

        # Resolve button
        self.resolve_btn = QPushButton("Resolve Selected Order")
        self.resolve_btn.setEnabled(False)
        self.resolve_btn.clicked.connect(self.resolve_selected_review)
        self.manual_review_layout.addWidget(self.resolve_btn)

        self.review_table.itemSelectionChanged.connect(
            lambda: self.resolve_btn.setEnabled(self.review_table.currentRow() >= 0)
        )

    def resolve_selected_review(self):

        row = self.review_table.currentRow()
        if row < 0:
            return

        order_id = self.review_table.item(row, 0).text()
        sku = self.review_table.item(row, 1).text()

        confirm = QMessageBox.question(
            self,
            "Confirm Resolution",
            f"Are you sure you want to resolve order '{order_id}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        result = resolve_manual_review(order_id, sku, self.user_id)
        if result.get("success"):
            QMessageBox.information(self, "Resolved", f"Order {order_id} has been marked as resolved.")
            self.load_manual_review_table()
            
        else:
            detail = result.get("detail", "Unknown error")
            QMessageBox.critical(self, "Error", f"Failed to resolve: {detail}")

    def on_tab_changed(self, index):
        if not getattr(self, "initialized", False):
            return  # Avoid premature tab loading during __init__

        tab_text = self.tabs.tabText(index)
        if tab_text == "Add Delivery":
            self.load_add_delivery_form()
        elif tab_text == "Manual Review":
            self.load_manual_review_table()

    def fix_missed_scan(self):

        row = self.review_table.currentRow()
        if row < 0:
            return

        order_id = self.review_table.item(row, 0).text()
        sku = self.review_table.item(row, 1).text()

        # Prompt for quantity
        quantity_str, ok = QInputDialog.getText(self, "Missing Quantity", "How many items are missing for this order?")
        if not ok:
            return

        if not quantity_str.strip().isdigit():
            QMessageBox.warning(self, "Invalid Input", "Please enter a whole number (e.g. 1, 2, 3).")
            return

        quantity = int(quantity_str.strip())
        if quantity <= 0:
            QMessageBox.warning(self, "Invalid Input", "Quantity must be greater than 0.")
            return

        scanned_serials = []

        # Pre-check: remove accidental logs if any exist for this order
        r_cleanup = requests.post(f"{API_BASE_URL}/clear-inventory-log", json={"order_id": order_id})
        if r_cleanup.status_code != 200:
            QMessageBox.warning(self, "Pre-check Failed", f"Could not clean previous logs:\n\n{r_cleanup.text}")
            return

        for i in range(quantity):
            while True:
                sn, ok = QInputDialog.getText(self, f"Serial {i+1} of {quantity}", f"Scan or enter serial number #{i+1}:")
                if not ok or not sn.strip():
                    QMessageBox.warning(self, "Cancelled", "Serial input cancelled.")
                    return

                serial_number = sn.strip()

                if serial_number in scanned_serials:
                    QMessageBox.warning(self, "Duplicate Serial", f"Serial '{serial_number}' already entered for this fix.")
                    continue  # Retry input

                # Step 1: Update inventory
                r1 = requests.post(f"{API_BASE_URL}/fix-serial-status", json={"serial_number": serial_number})
                if r1.status_code != 200:
                    QMessageBox.warning(self, "Invalid Serial", f"Could not mark serial as sold:\n\n{r1.text}")
                    continue  # Allow retry instead of canceling everything

                # Step 2: Insert into log
                r2 = requests.post(f"{API_BASE_URL}/insert-inventory-log", json={
                    "serial_number": serial_number,
                    "order_id": order_id
                })
                if r2.status_code != 200:
                    QMessageBox.warning(self, "Log Failure", f"Could not log serial:\n\n{r2.text}")
                    continue  # Allow retry instead of canceling everything

                scanned_serials.append(serial_number)
                break  # Proceed to next serial after successful insert

        # Step 3: Resolve manual review after all are successful
        result = resolve_manual_review(order_id, sku, self.user_id)
        if result.get("success"):
            QMessageBox.information(self, "Review Resolved", f"{quantity} serials logged. Review resolved.")
            self.load_manual_review_table()
        else:
            QMessageBox.warning(self, "Resolve Error", f"Partial success: Serials added, but resolve failed.\n{result.get('detail')}")

    def filter_master_skus(self):
        text = self.master_sku_search.text().strip().lower()

        if not hasattr(self, "full_master_sku_list"):
            return

        if not text:
            filtered = self.full_master_sku_list
        else:
            filtered = [
                msku for msku in self.full_master_sku_list
                if text in str(msku["master_sku_id"]).lower() or text in msku["description"].lower()
            ]

        self.master_sku_dropdown.clear()

        if not filtered:
            self.master_sku_dropdown.addItem("No matching results", -1)
            self.master_sku_dropdown.model().item(0).setEnabled(False)
            return

        for msku in filtered:
            label = f"{msku['master_sku_id']} – {msku['description']}"
            self.master_sku_dropdown.addItem(label, msku["master_sku_id"])
        
        self.master_sku_dropdown.setCurrentIndex(0)

    def reset_input_timer(self):
        text = self.serial_input.text().strip()
        if len(text) > 4:
            self.input_timer.start(50)

    def toggle_manual_mode(self):
        if self.manual_entry_checkbox.isChecked():
            try:
                self.serial_input.textChanged.disconnect(self.reset_input_timer)
            except Exception:
                pass
            self.serial_input.setPlaceholderText("Type full serial and press Enter")
            self.serial_input.returnPressed.connect(self.assign_serial)
        else:
            try:
                self.serial_input.returnPressed.disconnect(self.assign_serial)
            except Exception:
                pass
            self.serial_input.setPlaceholderText("Scan new serial number")
            self.serial_input.textChanged.connect(self.reset_input_timer)