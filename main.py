
import sys
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QLabel, QMessageBox
)
from PySide6.QtCore import Qt

def get_printers():
    cmd = [
        "powershell",
        "-Command",
        "Get-Printer | Select-Object -ExpandProperty Name"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return [x.strip() for x in result.stdout.splitlines() if x.strip()]

def get_default():
    cmd = [
        "powershell",
        "-Command",
        "(Get-CimInstance Win32_Printer | Where-Object {$_.Default -eq $true}).Name"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout.strip()

def set_default(printer_name):
    subprocess.run([
        "powershell",
        "-Command",
        f"Set-Printer -Name '{printer_name}' -IsDefault $true"
    ])

class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clinic Printer Switcher")
        self.resize(700, 500)

        self.layout = QVBoxLayout(self)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.label)

        self.list = QListWidget()
        self.layout.addWidget(self.list)

        self.btn = QPushButton("Сделать принтер основным")
        self.btn.clicked.connect(self.apply)
        self.layout.addWidget(self.btn)

        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.load)
        self.layout.addWidget(self.refresh_btn)

        self.setStyleSheet("""
        QWidget {
            background: #111827;
            color: #E5E7EB;
            font-size: 14px;
            font-family: Segoe UI;
        }

        QListWidget {
            background: #0F172A;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 8px;
        }

        QPushButton {
            background: #1D4ED8;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 10px;
            font-weight: bold;
        }

        QPushButton:hover {
            background: #2563EB;
        }

        QLabel {
            font-size: 18px;
            font-weight: bold;
            padding: 12px;
        }
        """)

        self.load()

    def load(self):
        self.list.clear()
        self.printers = get_printers()
        self.default = get_default()

        self.label.setText(f"Текущий принтер: {self.default}")

        for p in self.printers:
            self.list.addItem(p)

    def apply(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.warning(self, "Ошибка", "Выберите принтер")
            return

        printer = item.text()

        try:
            set_default(printer)
            QMessageBox.information(
                self,
                "Успешно",
                f"Принтер '{printer}' установлен по умолчанию"
            )
            self.load()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

app = QApplication(sys.argv)
window = Window()
window.show()
sys.exit(app.exec())
