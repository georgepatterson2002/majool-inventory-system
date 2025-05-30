import sys
print("main.py: starting")  # If this doesn't print, something in app/ is crashing

from PyQt5.QtWidgets import QApplication
from app.ui_main import MainWindow

print("main.py: creating QApplication")
app = QApplication(sys.argv)
print("main.py: QApplication created")

window = MainWindow()
window.show()
sys.exit(app.exec_())