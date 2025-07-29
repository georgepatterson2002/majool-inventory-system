import sys
print("main.py: starting")  # Debug marker

from PyQt5.QtWidgets import QApplication
from app.ui_main import MainWindow

print("main.py: creating QApplication")
app = QApplication(sys.argv)
print("main.py: QApplication created")

app.setStyleSheet("""
    QWidget {
        background-color: #F9FAFB;
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
        color: #374151;
    }

    QDialog, QTableWidget, QLineEdit, QComboBox, QTextEdit {
        background-color: #FFFFFF;
        border: 1px solid #D1D5DB;
        border-radius: 8px;
        padding: 6px;
        color: #374151;
    }

    /* Default app buttons */
    QPushButton {
        background-color: #0078D7;   /* Windows blue */
        color: white;
        border-radius: 8px;
        padding: 6px 12px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #0063B1;
        color: white;
    }
    QPushButton:disabled {
        background-color: #E5E7EB;
        color: #6B7280;
    }

    /* Dialog buttons (Confirm/Cancel, Yes/No, etc.) */
    QDialog QPushButton {
        background-color: #E5E7EB;   /* Neutral gray by default */
        color: #1F2937;
        border-radius: 6px;
        font-weight: bold;
    }
    QDialog QPushButton:hover {
        background-color: #0078D7;   /* Blue on hover */
        color: white;
    }
    QDialog QPushButton:default,
    QDialog QPushButton:focus {
        background-color: #0078D7;   /* Focused/default stays blue */
        color: white;
        font-weight: bold;
    }

    QLabel {
        color: #1F2937;
        font-weight: bold;
    }

    QTableWidget, QTableView {
        gridline-color: #E5E7EB;
        selection-background-color: #D1D5DB;  /* soft gray */
        selection-color: #1F2937;              /* dark gray text */
        border-radius: 6px;
    }

    QHeaderView::section {
        background-color: #F3F4F6;
        color: #374151;
        border: none;
        padding: 6px;
        font-weight: bold;
    }

    QScrollArea {
        border: none;
        background: transparent;
    }
                  
    QMenu {
        background-color: #FFFFFF;
        border: 1px solid #D1D5DB;
        border-radius: 6px;
        padding: 4px;
    }

    QMenu::item {
        padding: 6px 12px;
        color: #1F2937;  /* dark gray text */
        background-color: transparent;
    }

    QMenu::item:selected {
        background-color: #D1D5DB;  /* same soft gray as tables */
        color: #1F2937;
        border-radius: 4px;
    }

    QPushButton#logoutButton {
        background-color: #D1D5DB;    /* Neutral gray */
        color: #1F2937;               /* Dark gray text */
        border-radius: 8px;
        padding: 6px 12px;
        font-weight: bold;
    }

    QPushButton#logoutButton:hover {
        background-color: #9CA3AF;    /* Slightly darker on hover */
    }

    QPushButton#mainRefresh,
    QPushButton#manualReviewRefresh {
        background-color: #D1D5DB;    /* Neutral gray */
        color: #1F2937;               /* Dark gray text */
        border-radius: 8px;
        font-weight: bold;
        padding: 6px 12px;
    }

    QPushButton#mainRefresh:hover,
    QPushButton#manualReviewRefresh:hover {
        background-color: #9CA3AF;    /* Darker gray on hover */
        color: #1F2937;
    }

    QLabel#modeLabel {
        color: #1F2937;
        font-weight: bold;
        font-size: 14px;
    }
                  
   /* Make tabs bigger and text more readable */
    QTabBar::tab {
        background: #E5E7EB;
        padding: 4px 18px;                /* Less vertical height */
        margin-right: 8px;                /* Adds space between tabs */
        min-height: 22px;                 /* Shorter height */
        min-width: 120px;    
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        color: #374151;
        font-weight: bold;
    }

    QTabBar::tab:selected {
        background: #0078D7;
        color: white;
    }

    QTabBar::tab:hover {
        background: #0063B1;
        color: white;
    }

    QTabWidget::pane {
        border: 1px solid #D1D5DB;
        border-radius: 6px;
        background: #FFFFFF;
    }
""")

window = MainWindow()
window.show()
sys.exit(app.exec_())
