from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QLabel, QPushButton,
    QMessageBox, QFormLayout, QCheckBox
)
from PyQt5.QtCore import Qt
import bcrypt
import requests

from app.api_client import create_user  # You'll define this in the API client

class CreateUserForm(QWidget):
    def __init__(self, admin_user_id, refresh_callback=None):
        super().__init__()
        self.admin_user_id = admin_user_id
        self.refresh_callback = refresh_callback

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("e.g. johndoe")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Confirm Password")
        self.confirm_input.setEchoMode(QLineEdit.Password)

        self.admin_checkbox = QCheckBox("Grant admin access")

        self.submit_button = QPushButton("Create User")
        self.submit_button.clicked.connect(self.submit_user)

        layout = QFormLayout()
        layout.addRow("Username:", self.username_input)
        layout.addRow("Password:", self.password_input)
        layout.addRow("Confirm Password:", self.confirm_input)
        layout.addRow("", self.admin_checkbox)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)

    def submit_user(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        is_admin = self.admin_checkbox.isChecked()

        if not username or not password or not confirm:
            QMessageBox.warning(self, "Missing Fields", "All fields are required.")
            return

        if password != confirm:
            QMessageBox.critical(self, "Password Mismatch", "Passwords do not match.")
            return

        # Hash password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode()

        result = create_user(username, hashed, is_admin)
        if result["success"]:
            QMessageBox.information(self, "User Created", f"User '{username}' created successfully.")
            self.username_input.clear()
            self.password_input.clear()
            self.confirm_input.clear()
            self.admin_checkbox.setChecked(False)

            if self.refresh_callback:
                self.refresh_callback()

        else:
            QMessageBox.critical(self, "Error", result.get("detail", "Failed to create user."))
