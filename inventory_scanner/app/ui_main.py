from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QLineEdit
from PyQt5.QtGui import QIcon
from app.api_client import ping_server, login_user
from app.state_manager import AppState

print("ui_main.py: loaded")

class MainWindow(QMainWindow):
    def __init__(self):
        print("ui_main.py: file loaded")
        super().__init__()
        self.setWindowTitle("Majool SN Scanner")
        self.setWindowIcon(QIcon("assets/icon.ico"))
        self.setFixedSize(300, 250)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self.handle_login)

        self.username_input.returnPressed.connect(self.handle_login)
        self.password_input.returnPressed.connect(self.handle_login)

        self.status_label = QLabel("Status: Disconnected")
        self.connect_button = QPushButton("Connect to Server")
        self.connect_button.clicked.connect(self.check_server)
        self.connect_button.setAutoDefault(True)
        self.connect_button.setDefault(True)
        self.connect_button.setFocus()

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.connect_button)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Hide login inputs until server is connected
        self.username_input.hide()
        self.password_input.hide()
        self.login_button.hide()

    def check_server(self):
        if ping_server():
            self.status_label.setText("Status: Connected")
            self.connect_button.hide()
            self.username_input.show()
            self.password_input.show()
            self.login_button.show()
            self.username_input.setFocus()
        else:
            self.status_label.setText("Status: Disconnected")

    def handle_login(self):
        from app.inventory_view import InventoryView

        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        result = login_user(username, password)
        if result["success"]:
            user_id = result["user_id"]
            is_admin = result.get("is_admin", False)  # Safely default to False

            AppState.login(username, user_id, is_admin)
            self.status_label.setText(f"Logged in as: {username}")
            self.connect_button.setDisabled(True)
            self.login_button.setDisabled(True)
            self.username_input.setDisabled(True)
            self.password_input.setDisabled(True)

            self.inventory_window = InventoryView(user_id, is_admin)
            self.inventory_window.show()
            self.close()
        else:
            self.status_label.setText("Login failed")

