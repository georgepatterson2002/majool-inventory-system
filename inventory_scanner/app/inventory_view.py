from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QMessageBox, QAbstractItemView, QTabWidget,
    QComboBox, QTableWidgetItem, QHeaderView, QDialog, QInputDialog, QFormLayout,
    QCheckBox, QHBoxLayout, QSizePolicy, QMenu, QApplication
)
import webbrowser
from PyQt5.QtGui import QFont, QIcon, QPalette, QColor
from PyQt5.QtMultimedia import QSoundEffect
from PyQt5.QtCore import Qt, QUrl, QTimer, QSize
import requests
import os
from dotenv import load_dotenv
from app.api_client import fetch_master_skus, fetch_categories, fetch_brands, fetch_manual_reviews, resolve_manual_review, create_master_sku, fetch_ssd_types, fetch_product_list
from app.create_user_window import CreateUserForm
from app.damaged_items_tab import DamagedItemsTab
from app.reconciled_items_tab import ReconciledItemsTab
from app.MissingSerialDialog import MissingSerialDialog
from app.AddManualOrderDialog import AddManualOrderDialog
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
        self.toggle_button = QPushButton("-- More Tools --")
        self.toggle_button.clicked.connect(self.toggle_mode)

        self.logout_button = QPushButton("Logout")
        self.logout_button.setObjectName("logoutButton")
        self.logout_button.clicked.connect(self.handle_logout)
        self.logout_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # ------------------ SCAN MODE ------------------ #
        self.status_label = QLabel("Loading units...")
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_edit_context_menu)

        
        self.refresh_button = QPushButton("Refresh Table")
        self.refresh_button.setObjectName("mainRefresh")
        self.refresh_button.setIcon(QIcon("assets/refresh.svg"))
        self.refresh_button.setIconSize(QSize(24, 24))
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
        self.manual_entry_checkbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.mistake_mode_checkbox = QCheckBox("Mistake Mode")
        self.mistake_mode_checkbox.setToolTip("Ignore return prompts until a valid serial is scanned.")
        self.mistake_mode_checkbox.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        checkbox_row = QHBoxLayout()
        checkbox_row.setSpacing(1)  #  smaller spacing between checkboxes
        checkbox_row.setContentsMargins(0, 0, 0, 0)  #  no outer padding
        checkbox_row.addWidget(self.manual_entry_checkbox)
        checkbox_row.addWidget(self.mistake_mode_checkbox)

        checkbox_row.addStretch()

        self.scan_layout.addLayout(checkbox_row)

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
        self.tab_damaged = DamagedItemsTab()
        self.tab_reconciled = ReconciledItemsTab()
        
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.tabs.addTab(self.tab_delivery, "Add Delivery")

        if is_admin:
            self.tabs.addTab(self.tab_product, "Add SKU")
            self.tabs.addTab(self.tab_manual_review, "Manual Review")
            self.tabs.addTab(self.tab_damaged, "Damaged Items")
            self.tabs.addTab(self.tab_reconciled, "Reconciled Items")
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

        self.is_ssd_checkbox = QCheckBox("This product is a type of memory")
        self.is_ssd_checkbox.stateChanged.connect(self.toggle_ssd_dropdown)

        self.ssd_type_dropdown = QComboBox()
        self.ssd_type_dropdown.setEnabled(False)

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

        self.product_layout.addRow(self.is_ssd_checkbox, self.ssd_type_dropdown)
        self.product_layout.addWidget(self.product_submit_button)

        # ------------------ MAIN LAYOUT ------------------ #

        # Top bar with SCAN label on the left and Logout on the right
        top_bar = QHBoxLayout()

        self.mode_label = QLabel("SCAN:")
        self.mode_label.setObjectName("modeLabel")
        font = self.mode_label.font()
        font.setBold(True)
        self.mode_label.setFont(font)

        top_bar.addWidget(self.mode_label)    # left-aligned "SCAN:" label
        top_bar.addStretch()                  # push logout to far right
        top_bar.addWidget(self.logout_button)

        layout = QVBoxLayout()
        layout.addLayout(top_bar)             # add top bar first
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

        self.full_product_list = fetch_product_list()


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
            "Unit ID", "PO Number", "SN Prefix" 
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
                row["po_number"],
                row["sn_prefix"] or ""
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

                if self.mistake_mode_checkbox.isChecked():
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Information)
                    msg.setWindowTitle("Valid Serial Found")
                    msg.setText(f"Serial '{new_serial}' accepted.\nExiting Mistake Mode.")
                    ok_btn = msg.addButton("OK", QMessageBox.AcceptRole)
                    msg.setDefaultButton(None)
                    ok_btn.setFocusPolicy(Qt.NoFocus)
                    msg.setWindowModality(Qt.ApplicationModal)
                    msg.raise_()
                    msg.activateWindow()
                    msg.exec_()

                    self.serial_input.setFocus()
                    self.mistake_mode_checkbox.setChecked(False)

                return

            else:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception as e:
                    detail = f"Unexpected response from server (status {response.status_code})"

                print(f"[ERROR] assign_serial failed: {detail}")

                if "Serial number already exists" in detail:
                    if self.mistake_mode_checkbox.isChecked():
                        self.error_sound.play()
                        self.serial_input.clear()
                        self.focus_serial_input()
                        return

                    # Duplicate serial - offer return
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Question)
                    box.setWindowTitle("Duplicate Serial Detected")
                    box.setText(
                        f"Serial '{new_serial}' already exists and may have been sold.\n\nWould you like to process this as a return?"
                    )
                    yes_btn = box.addButton("Yes", QMessageBox.YesRole)
                    no_btn = box.addButton("No", QMessageBox.NoRole)
                    box.setDefaultButton(None)
                    yes_btn.setFocusPolicy(Qt.NoFocus)
                    no_btn.setFocusPolicy(Qt.NoFocus)
                    box.setWindowModality(Qt.ApplicationModal)
                    box.raise_()
                    box.activateWindow()
                    box.exec_()

                    if box.clickedButton() == yes_btn:
                        try:
                            return_response = requests.post(f"{API_BASE_URL}/handle-return-scan", json={
                                "scanned_serial": new_serial,
                                "placeholder_unit_id": unit_id,
                                "user_id": self.user_id
                            })

                            if return_response.status_code == 200:
                                self.serial_input.clear()
                                self.load_data()
                                self.select_first_valid_row()
                                self.focus_serial_input()

                                if self.mistake_mode_checkbox.isChecked():
                                    msg = QMessageBox(self)
                                    msg.setIcon(QMessageBox.Information)
                                    msg.setWindowTitle("Valid Serial Found")
                                    msg.setText(f"Serial '{new_serial}' accepted.\nExiting Mistake Mode.")
                                    ok_btn = msg.addButton("OK", QMessageBox.AcceptRole)
                                    msg.setDefaultButton(None)
                                    ok_btn.setFocusPolicy(Qt.NoFocus)
                                    msg.setWindowModality(Qt.ApplicationModal)
                                    msg.raise_()
                                    msg.activateWindow()
                                    msg.exec_()
                                    self.mistake_mode_checkbox.setChecked(False)

                                return  # ← CRITICAL: prevents fallback to /assign-serial after return
                            else:
                                msg = return_response.json().get("detail", "Unknown error")
                                QMessageBox.critical(self, "Return Failed", f"Failed to process return:\n\n{msg}")
                                return  # ← PREVENTS FALLBACK attempt after failure
                        except Exception as e:
                            QMessageBox.critical(self, "Request Error", f"Error contacting server:\n{str(e)}")
                            return  # ← PREVENTS FALLBACK
                    else:
                        self.error_sound.play()
                        show_strict_error_dialog(self, new_serial, detail)

                else:
                    #  Show any other error — including prefix mismatch
                    self.error_sound.play()
                    show_strict_error_dialog(self, new_serial, detail)

                self.serial_input.clear()
                self.select_first_valid_row()
                self.focus_serial_input()
                return

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
            self.mode_label.setText("TOOLS:")
            current_index = self.tabs.currentIndex()
            self.on_tab_changed(current_index)
        else:
            self.delivery_container.hide()
            self.scan_container.show()
            self.toggle_button.setText("-- More Tools --")
            self.mode_label.setText("SCAN:")
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
        self.delivery_form = AddDeliveryForm(
            self.user_id,
            self.handle_delivery_submitted,
            damaged_tab=self.tab_damaged
        )

        self.delivery_layout.addWidget(self.delivery_form)
    
    def handle_delivery_submitted(self, go_to_scan=False):
        self.load_data()
        if go_to_scan:
            self.toggle_mode()
        

    def load_product_form_dropdowns(self):

        self.full_master_sku_list = fetch_master_skus()
        ssd_types = fetch_ssd_types()

        self.master_sku_dropdown.clear()
        self.category_dropdown.clear()
        self.brand_dropdown.clear()
        self.ssd_type_dropdown.clear()

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

        for ssd in ssd_types:
         self.ssd_type_dropdown.addItem(ssd["label"], ssd["ssd_id"])

        self.category_dropdown.setCurrentIndex(default_index)
   
    def submit_product(self):

        from app.api_client import add_product

        part_number = self.part_number_input.text().strip()
        product_name = self.product_name_input.text().strip()
        brand = self.brand_dropdown.currentData()
        master_sku_id = self.master_sku_dropdown.currentData()
        category_id = self.category_dropdown.currentData()

        ssd_id = None
        if self.is_ssd_checkbox.isChecked():
            ssd_id = self.ssd_type_dropdown.currentData()

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


        result = add_product(part_number, product_name, brand, master_sku_id, category_id, ssd_id)

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

        # Refresh button at the top
        refresh_btn = QPushButton("Refresh Table")
        refresh_btn.setObjectName("manualReviewRefresh")
        refresh_btn.setIcon(QIcon("assets/refresh.svg"))
        refresh_btn.setIconSize(QSize(24, 24))
        refresh_btn.clicked.connect(self.load_manual_review_table)
        self.manual_review_layout.addWidget(refresh_btn)

        # Apply icon/text color to THIS button
        palette2 = refresh_btn.palette()
        palette2.setColor(QPalette.ButtonText, QColor("#1F2937"))
        refresh_btn.setPalette(palette2)

        # Table in the middle
        self.review_table = QTableWidget()
        self.review_table.setColumnCount(3)
        self.review_table.setHorizontalHeaderLabels(["Order ID", "SKU", "Created At"])
        self.review_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.review_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.review_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.review_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.review_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.review_table.customContextMenuRequested.connect(self.open_review_context_menu)

        reviews = fetch_manual_reviews()
        self.review_table.setRowCount(len(reviews))

        for row_idx, item in enumerate(reviews):
            self.review_table.setItem(row_idx, 0, QTableWidgetItem(item["order_id"]))
            self.review_table.setItem(row_idx, 1, QTableWidgetItem(item["sku"]))
            self.review_table.setItem(row_idx, 2, QTableWidgetItem(item["created_at"]))

        self.manual_review_layout.addWidget(self.review_table)

        # --- Load icons (active + disabled) ---
        icon_enter_active = QIcon("assets/icon_enter.png")
        icon_enter_disabled = QIcon("assets/icon_enter_disabled.png")

        icon_check_active = QIcon("assets/icon_check.png")
        icon_check_disabled = QIcon("assets/icon_check_disabled.png")

        icon_plus_active = QIcon("assets/plus.png")
        # (Add Manual Order is usually always active, so no disabled icon needed)

        # Action buttons BELOW the table
        self.fix_btn = QPushButton("Enter Order Details")
        self.fix_btn.setIcon(icon_enter_disabled)  # start disabled
        self.fix_btn.setIconSize(QSize(24, 24))
        self.fix_btn.setEnabled(False)
        self.fix_btn.clicked.connect(self.fix_missed_scan)
        self.manual_review_layout.addWidget(self.fix_btn)

        self.resolve_btn = QPushButton("Mark as Resolved")
        self.resolve_btn.setIcon(icon_check_disabled)  # start disabled
        self.resolve_btn.setIconSize(QSize(24, 24))
        self.resolve_btn.setEnabled(False)
        self.resolve_btn.clicked.connect(self.resolve_selected_review)
        self.manual_review_layout.addWidget(self.resolve_btn)

        self.add_manual_order_btn = QPushButton("Add Manual Order")
        self.add_manual_order_btn.setIcon(icon_plus_active)
        self.add_manual_order_btn.setIconSize(QSize(24, 24))
        self.add_manual_order_btn.clicked.connect(self.open_add_manual_order)
        self.manual_review_layout.addWidget(self.add_manual_order_btn)

        # --- Function to update icons when enabled/disabled ---
        def update_manual_review_icons():
            self.fix_btn.setIcon(icon_enter_active if self.fix_btn.isEnabled() else icon_enter_disabled)
            self.resolve_btn.setIcon(icon_check_active if self.resolve_btn.isEnabled() else icon_check_disabled)

        # 🔹 Enable/disable buttons based on selection
        def on_selection_changed():
            enabled = self.review_table.currentRow() >= 0
            self.resolve_btn.setEnabled(enabled)
            self.fix_btn.setEnabled(enabled)
            update_manual_review_icons()

        self.review_table.itemSelectionChanged.connect(on_selection_changed)

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

        result = resolve_manual_review(order_id, sku, self.user_id, 0)
        if result.get("success"):
            QMessageBox.information(self, "Resolved", f"Order {order_id} has been marked as resolved.")
            self.load_manual_review_table()
            
        else:
            detail = result.get("detail", "Unknown error")
            QMessageBox.critical(self, "Error", f"Failed to resolve: {detail}")

    def on_tab_changed(self, index):
        if not getattr(self, "initialized", False):
            return  # Prevents premature loading during __init__

        tab_text = self.tabs.tabText(index)

        if tab_text == "Add Delivery":
            self.load_add_delivery_form()
        elif tab_text == "Manual Review":
            self.load_manual_review_table()
        elif tab_text == "Damaged Items" and hasattr(self, "tab_damaged"):
            self.tab_damaged.load_damaged_units()
        elif tab_text == "Reconciled Items" and hasattr(self, "tab_reconciled"):
            self.tab_reconciled.load_data()

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

        # Ask if user has serials
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Serials Available?")
        box.setText("Do you have the serial numbers to scan?\n\nClick 'Yes' to scan serials, or 'No' to log as human error (no serials).")

        yes_btn = box.addButton("Yes", QMessageBox.YesRole)
        no_btn = box.addButton("No", QMessageBox.NoRole)

        # Prevent any button from being focused by default
        box.setDefaultButton(None)
        box.setEscapeButton(None)

        # Optional but helps ensure no visual highlight
        yes_btn.setAutoDefault(False)
        no_btn.setAutoDefault(False)
        yes_btn.clearFocus()
        no_btn.clearFocus()
        box.setFocus()

        box.exec_()

        if box.clickedButton() == no_btn:
            from app.api_client import log_untracked_sale

            dialog = MissingSerialDialog(order_id=order_id, quantity=quantity)
            if dialog.exec_() == QDialog.Accepted:
                product_id = dialog.selected_product_id
                result = log_untracked_sale(product_id, order_id, quantity)

                if result.get("success"):
                    resolve_result = resolve_manual_review(order_id, sku, self.user_id, 0)
                    if resolve_result.get("success"):
                        QMessageBox.information(self, "Review Resolved", "Human error logged and review resolved.")
                    else:
                        QMessageBox.warning(self, "Log Saved", f"Logged, but resolve failed: {resolve_result.get('detail')}")
                    self.load_manual_review_table()
                else:
                    QMessageBox.critical(self, "Error", f"Failed to log missing serial: {result.get('detail', 'Unknown error')}")
            return

        # ==== Scan serials ====
        scanned_serials = []

        # Clear any previous inventory logs for this order
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
                    QMessageBox.warning(self, "Duplicate Serial", f"Serial '{serial_number}' already entered.")
                    continue

                r1 = requests.post(f"{API_BASE_URL}/fix-serial-status", json={"serial_number": serial_number})
                if r1.status_code != 200:
                    QMessageBox.warning(self, "Invalid Serial", f"Could not mark serial as sold:\n\n{r1.text}")
                    continue

                r2 = requests.post(f"{API_BASE_URL}/insert-inventory-log", json={
                    "serial_number": serial_number,
                    "order_id": order_id
                })
                if r2.status_code != 200:
                    QMessageBox.warning(self, "Log Failure", f"Could not log serial:\n\n{r2.text}")
                    continue

                scanned_serials.append(serial_number)
                break

        result = resolve_manual_review(order_id, sku, self.user_id, quantity)
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

    def toggle_ssd_dropdown(self):
     self.ssd_type_dropdown.setEnabled(self.is_ssd_checkbox.isChecked())

    def open_edit_context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        unit_id_item = self.table.item(row, 3)
        if not unit_id_item or not unit_id_item.text().isdigit():
            return  # Skip group header rows

        unit_id = int(unit_id_item.text())
        po_item = self.table.item(row, 4)
        po_current = po_item.text() if po_item else ""

        try:
            res = requests.get(f"{API_BASE_URL}/noser-units")
            sn_prefix = ""
            for unit in res.json():
                if int(unit["unit_id"]) == unit_id:
                    sn_prefix = unit.get("sn_prefix") or ""
                    break
        except Exception as e:
            sn_prefix = ""

        # Build context menu
        menu = QMenu(self)
        edit_sn_action = menu.addAction("Change SN Prefix")
        edit_po_action = menu.addAction("Change PO Number")
        menu.addSeparator()
        bulk_edit_action = menu.addAction("Bulk Edit All Displayed Units")  # Add this

        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action == edit_sn_action:
            self.edit_sn_prefix(unit_id, sn_prefix)
        elif action == edit_po_action:
            self.edit_po_number(unit_id, po_current)
        elif action == bulk_edit_action:
            self.open_bulk_edit_dialog()  # Trigger dialog method


    def edit_sn_prefix(self, unit_id, current_value):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Edit SN Prefix")
        msg_box.setText(f"Current SN Prefix: {current_value or '[None]'}\n\nWhat would you like to do?")
        edit_btn = msg_box.addButton("Edit", QMessageBox.AcceptRole)
        clear_btn = msg_box.addButton("Clear", QMessageBox.DestructiveRole)
        cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole)
        msg_box.exec_()

        clicked = msg_box.clickedButton()
        if clicked == cancel_btn:
            return
        elif clicked == clear_btn:
            sn_prefix = ""
        else:
            # Custom input dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Enter SN Prefix")
            layout = QVBoxLayout(dialog)

            input_field = QLineEdit()
            input_field.setMaxLength(2)
            input_field.setPlaceholderText("e.g. CN or A1")
            layout.addWidget(input_field)

            button_row = QHBoxLayout()
            confirm = QPushButton("OK")
            cancel = QPushButton("Cancel")
            confirm.clicked.connect(dialog.accept)
            cancel.clicked.connect(dialog.reject)
            button_row.addWidget(confirm)
            button_row.addWidget(cancel)
            layout.addLayout(button_row)

            dialog.setLayout(layout)

            if dialog.exec_() != QDialog.Accepted:
                return

            sn_prefix = input_field.text().strip()
            if len(sn_prefix) != 2 or not sn_prefix.isalnum():
                QMessageBox.warning(self, "Invalid Input", "SN Prefix must be exactly 2 alphanumeric characters.")
                return

        # Send to backend
        try:
            response = requests.post(f"{API_BASE_URL}/update-unit-meta", json={
                "unit_id": unit_id,
                "sn_prefix": sn_prefix,
                "po_number": None,
                "user_id": self.user_id
            })
            if response.status_code == 200:
                msg = "SN Prefix cleared." if sn_prefix == "" else f"SN Prefix updated to '{sn_prefix}'"
                QMessageBox.information(self, "Success", msg)
                self.load_data()
            else:
                detail = response.json().get("detail", response.text)
                QMessageBox.warning(self, "Error", f"Update failed:\n{detail}")
        except Exception as e:
            QMessageBox.critical(self, "Request Error", f"Error: {str(e)}")



    def edit_po_number(self, unit_id, current_value):
        new_value, ok = QInputDialog.getText(
            self, "Edit PO Number", f"Current: {current_value}\nNew PO Number:"
        )
        if not ok or not new_value.strip():
            return

        try:
            response = requests.post(f"{API_BASE_URL}/update-unit-meta", json={
                "unit_id": unit_id,
                "sn_prefix": None,
                "po_number": new_value.strip(),
                "user_id": self.user_id
            })
            if response.status_code == 200:
                QMessageBox.information(self, "Success", f"PO Number updated to '{new_value.strip()}'")
                self.load_data()
            else:
                detail = response.json().get("detail", response.text)
                QMessageBox.warning(self, "Error", f"Update failed:\n{detail}")
        except Exception as e:
            QMessageBox.critical(self, "Request Error", f"Error: {str(e)}")

    def open_bulk_edit_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Bulk Update All NOSER Units")
        dialog.resize(400, 160)

        layout = QFormLayout(dialog)

        sn_input = QLineEdit()
        sn_input.setPlaceholderText("Leave blank to keep existing")
        sn_input.setMaxLength(2)
        #sn_input.setInputMask(">AA")  # force uppercase, alphanumeric

        po_input = QLineEdit()
        po_input.setPlaceholderText("Leave blank to keep existing")
        po_input.setMaxLength(32)

        layout.addRow("New SN Prefix:", sn_input)
        layout.addRow("New PO Number:", po_input)

        button_row = QHBoxLayout()
        apply_btn = QPushButton("Apply")
        cancel_btn = QPushButton("Cancel")
        button_row.addWidget(apply_btn)
        button_row.addWidget(cancel_btn)
        layout.addRow(button_row)

        apply_btn.clicked.connect(lambda: self.perform_bulk_update(
            sn_input.text().strip() or None,
            po_input.text().strip() or None,
            dialog
        ))
        cancel_btn.clicked.connect(dialog.reject)

        dialog.setLayout(layout)
        dialog.exec_()
    
    def perform_bulk_update(self, sn_prefix, po_number, dialog):
        # --- Validation ---
        if sn_prefix:
            if len(sn_prefix) != 2 or not sn_prefix.isalnum():
                QMessageBox.warning(self, "Invalid SN Prefix", "SN Prefix must be exactly 2 alphanumeric characters.")
                return

        if po_number:
            if len(po_number) < 3:
                QMessageBox.warning(self, "Invalid PO Number", "PO Number must be at least 3 characters.")
                return
            if po_number.startswith("11-") or po_number.count("-") >= 2:
                QMessageBox.warning(self, "Invalid PO Number", "PO Number looks like an Order ID. Please enter a valid PO.")
                return

        # --- Send to backend ---
        try:
            response = requests.post(f"{API_BASE_URL}/bulk-update-units", json={
                "sn_prefix": sn_prefix,
                "po_number": po_number,
                "user_id": self.user_id
            })
            if response.status_code == 200:
                updated = response.json().get("updated", "?")
                QMessageBox.information(self, "Success", f"{updated} units updated.")
                dialog.accept()
                self.load_data()
            else:
                detail = response.json().get("detail", response.text)
                QMessageBox.warning(self, "Failed", f"Bulk update failed:\n\n{detail}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Request error:\n\n{str(e)}")

    def open_review_context_menu(self, pos):
        row = self.review_table.rowAt(pos.y())
        if row < 0:
            return

        order_id_item = self.review_table.item(row, 0)
        if not order_id_item:
            return

        order_id = order_id_item.text()

        menu = QMenu(self)
        copy_order_id_action = menu.addAction("Copy Order ID")
        search_amazon_action = menu.addAction("Search on Amazon")

        action = menu.exec_(self.review_table.viewport().mapToGlobal(pos))

        if action == copy_order_id_action:
            QApplication.clipboard().setText(order_id)
        elif action == search_amazon_action:
            import webbrowser
            webbrowser.open(f"https://sellercentral.amazon.com/orders-v3/order/{order_id}")

    def open_add_manual_order(self):
        dialog = AddManualOrderDialog(self.full_product_list, self)
        dialog.exec_()