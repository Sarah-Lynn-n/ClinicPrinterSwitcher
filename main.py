import json
import os
import sys
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QDialog,
    QLineEdit,
    QFormLayout,
    QCheckBox,
    QDialogButtonBox,
)

APP_DIR = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "ClinicPrinterSwitcher"
CONFIG_PATH = APP_DIR / "printers.json"
LOG_PATH = APP_DIR / "clinic_printer_switcher.log"

DEFAULT_CONFIG = {
    "admin_pin": "2468",
    "hide_unknown_printers_for_users": False,
    "known_printers": {},
    "browser_profiles": {
        "yandex": True,
        "chrome": True,
        "edge": True
    }
}


@dataclass
class PrinterInfo:
    system_name: str
    display_name: str
    is_default: bool
    is_known: bool


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)


def log(message: str) -> None:
    ensure_app_dir()
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def load_config() -> dict:
    ensure_app_dir()
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = DEFAULT_CONFIG.copy()

    cfg.setdefault("admin_pin", "2468")
    cfg.setdefault("hide_unknown_printers_for_users", False)
    cfg.setdefault("known_printers", {})
    cfg.setdefault("browser_profiles", {"yandex": True, "chrome": True, "edge": True})
    return cfg


def save_config(cfg: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def run_powershell(command: str) -> str:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    return result.stdout.strip()


def get_default_printer_name() -> Optional[str]:
    ps = "(Get-CimInstance Win32_Printer | Where-Object {$_.Default -eq $true} | Select-Object -First 1 -ExpandProperty Name)"
    out = run_powershell(ps)
    return out.strip() if out.strip() else None


def get_system_printers() -> List[str]:
    ps = "Get-Printer | Sort-Object Name | Select-Object -ExpandProperty Name"
    out = run_powershell(ps)
    return [line.strip() for line in out.splitlines() if line.strip()]


def cleanup_printer_name(name: str) -> str:
    cleaned = name
    junk_tokens = [
        " Series",
        " Class Driver",
        " PCL6",
        " PCL",
        " XPS",
        " V4",
        " Driver"
    ]

    for token in junk_tokens:
        cleaned = cleaned.replace(token, "")

    return " ".join(cleaned.split())


def get_printer_infos(cfg: dict) -> List[PrinterInfo]:
    known: Dict[str, str] = cfg.get("known_printers", {})
    default_name = get_default_printer_name()
    infos: List[PrinterInfo] = []

    for system_name in get_system_printers():
        is_known = system_name in known
        display_name = known.get(system_name, cleanup_printer_name(system_name))

        infos.append(
            PrinterInfo(
                system_name=system_name,
                display_name=display_name,
                is_default=(system_name == default_name),
                is_known=is_known,
            )
        )

    return infos


def disable_windows_auto_default_printer() -> None:
    run_powershell(
        "Set-ItemProperty -Path 'HKCU:\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Windows' "
        "-Name LegacyDefaultPrinterMode -Value 1"
    )


def set_windows_default_printer(system_name: str) -> None:
    escaped = system_name.replace("'", "''")
    disable_windows_auto_default_printer()
    run_powershell(f"Set-Printer -Name '{escaped}' -IsDefault $true")


def browser_preference_paths(cfg: dict) -> List[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    paths: List[Path] = []
    bp = cfg.get("browser_profiles", {})

    candidates = {
        "yandex": local / "Yandex" / "YandexBrowser" / "User Data",
        "chrome": local / "Google" / "Chrome" / "User Data",
        "edge": local / "Microsoft" / "Edge" / "User Data",
    }

    for key, root in candidates.items():
        if not bp.get(key, False) or not root.exists():
            continue

        for profile_dir in root.iterdir():
            if profile_dir.is_dir() and (profile_dir.name == "Default" or profile_dir.name.startswith("Profile")):
                pref = profile_dir / "Preferences"
                if pref.exists():
                    paths.append(pref)

    return paths


def patch_browser_printer_preferences(system_name: str, cfg: dict) -> int:
    changed = 0

    for path in browser_preference_paths(cfg):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            printing = data.setdefault("printing", {})
            sticky = printing.setdefault("print_preview_sticky_settings", {})

            app_state_raw = sticky.get("appState", "{}")
            try:
                app_state = json.loads(app_state_raw)
            except Exception:
                app_state = {}

            app_state["selectedDestinationId"] = system_name
            app_state["recentDestinations"] = [
                {
                    "id": system_name,
                    "origin": "local",
                    "account": "",
                }
            ]

            sticky["appState"] = json.dumps(app_state, ensure_ascii=False, separators=(",", ":"))
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            changed += 1

        except Exception as e:
            log(f"Browser preferences patch failed for {path}: {e}")

    return changed


class PinDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Админ-доступ")
        self.setModal(True)

        layout = QFormLayout(self)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("PIN")

        layout.addRow("PIN:", self.pin_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    @property
    def pin(self) -> str:
        return self.pin_input.text().strip()


class AdminDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg

        self.setWindowTitle("Администрирование принтеров")
        self.resize(740, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel("Добавление и переименование принтеров")
        title.setObjectName("AdminTitle")
        layout.addWidget(title)

        hint = QLabel(
            "Выберите системный принтер, задайте понятное имя и нажмите «Сохранить». "
            "На основном экране врачи будут видеть понятные имена."
        )
        hint.setObjectName("AdminHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.admin_list = QListWidget()
        layout.addWidget(self.admin_list, 1)

        form = QFormLayout()

        self.system_name = QLineEdit()
        self.system_name.setReadOnly(True)

        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("Например: Регистратура / Кабинет врача / PDF")

        form.addRow("Системное имя:", self.system_name)
        form.addRow("Понятное имя:", self.display_name)

        layout.addLayout(form)

        self.hide_unknown = QCheckBox("На основном экране показывать только добавленные принтеры")
        layout.addWidget(self.hide_unknown)

        buttons = QHBoxLayout()

        self.refresh_button = QPushButton("Обнаружить принтеры")
        self.save_button = QPushButton("Сохранить имя")
        self.close_button = QPushButton("Закрыть")

        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.save_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)

        layout.addLayout(buttons)

        self.admin_list.currentItemChanged.connect(self.on_select)
        self.refresh_button.clicked.connect(self.refresh)
        self.save_button.clicked.connect(self.save_name)
        self.close_button.clicked.connect(self.accept)
        self.hide_unknown.stateChanged.connect(self.save_hide_unknown)

        self.refresh()

    def refresh(self):
        self.cfg = load_config()
        self.hide_unknown.setChecked(bool(self.cfg.get("hide_unknown_printers_for_users", False)))
        self.admin_list.clear()

        try:
            infos = get_printer_infos(self.cfg)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить список принтеров:\n{e}")
            return

        for p in infos:
            item = QListWidgetItem(self.format_admin_item(p))
            item.setData(Qt.UserRole, p.system_name)
            self.admin_list.addItem(item)

    def format_admin_item(self, p: PrinterInfo) -> str:
        status = "по умолчанию" if p.is_default else ""
        known = "добавлен" if p.is_known else "новый"
        return f"{p.display_name}  ·  {known}  ·  {status}\n{p.system_name}"

    def on_select(self, current, previous):
        if not current:
            self.system_name.clear()
            self.display_name.clear()
            return

        system_name = current.data(Qt.UserRole)
        known = self.cfg.setdefault("known_printers", {})

        self.system_name.setText(system_name)
        self.display_name.setText(known.get(system_name, cleanup_printer_name(system_name)))

    def save_name(self):
        system_name = self.system_name.text().strip()
        display_name = self.display_name.text().strip()

        if not system_name or not display_name:
            QMessageBox.information(self, "Принтер", "Выберите принтер и укажите понятное имя.")
            return

        self.cfg.setdefault("known_printers", {})[system_name] = display_name
        save_config(self.cfg)

        QMessageBox.information(self, "Готово", "Имя принтера сохранено.")
        self.refresh()

    def save_hide_unknown(self):
        self.cfg["hide_unknown_printers_for_users"] = self.hide_unknown.isChecked()
        save_config(self.cfg)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.cfg = load_config()

        self.setWindowTitle("Clinic Printer Switcher")
        self.resize(720, 460)

        self.build_ui()
        self.apply_theme()
        self.refresh()

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main = QVBoxLayout(root)
        main.setContentsMargins(24, 22, 24, 22)
        main.setSpacing(16)

        header = QHBoxLayout()

        title_box = QVBoxLayout()

        title = QLabel("Clinic Printer Switcher")
        title.setObjectName("Title")

        subtitle = QLabel("Выберите принтер и сделайте его основным")
        subtitle.setObjectName("Subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header.addLayout(title_box)
        header.addStretch()

        self.gear_button = QPushButton("⚙")
        self.gear_button.setObjectName("GearButton")
        self.gear_button.setFixedSize(46, 42)
        self.gear_button.clicked.connect(self.open_admin)

        header.addWidget(self.gear_button)

        main.addLayout(header)

        self.current_label = QLabel("Текущий принтер: —")
        self.current_label.setObjectName("CurrentPrinter")
        main.addWidget(self.current_label)

        self.printer_list = QListWidget()
        self.printer_list.itemDoubleClicked.connect(self.set_selected_printer)
        main.addWidget(self.printer_list, 1)

        buttons = QHBoxLayout()

        self.set_button = QPushButton("Сделать выбранный принтер основным")
        self.set_button.clicked.connect(self.set_selected_printer)

        self.refresh_button = QPushButton("Обновить список")
        self.refresh_button.clicked.connect(self.refresh)

        buttons.addWidget(self.set_button, 2)
        buttons.addWidget(self.refresh_button, 1)

        main.addLayout(buttons)

    def apply_theme(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #111827;
                color: #E5E7EB;
                font-family: Segoe UI;
                font-size: 14px;
            }

            QLabel#Title {
                font-size: 26px;
                font-weight: 700;
                color: #F9FAFB;
            }

            QLabel#Subtitle, QLabel#AdminHint {
                font-size: 13px;
                color: #93A4B8;
            }

            QLabel#AdminTitle {
                font-size: 20px;
                font-weight: 700;
                color: #F9FAFB;
            }

            QLabel#CurrentPrinter {
                background: #1F2937;
                border: 1px solid #2F3B4D;
                border-radius: 14px;
                padding: 16px;
                font-size: 18px;
                font-weight: 600;
                color: #BFDBFE;
            }

            QListWidget {
                background: #0B1220;
                border: 1px solid #243244;
                border-radius: 14px;
                padding: 8px;
                outline: none;
            }

            QListWidget::item {
                padding: 14px;
                margin: 4px;
                border-radius: 10px;
            }

            QListWidget::item:selected {
                background: #1D4ED8;
                color: #FFFFFF;
            }

            QPushButton {
                background: #1E3A8A;
                color: #FFFFFF;
                border: none;
                border-radius: 12px;
                padding: 11px 16px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #2563EB;
            }

            QPushButton#GearButton {
                background: #1F2937;
                font-size: 20px;
                border: 1px solid #374151;
            }

            QPushButton#GearButton:hover {
                background: #263449;
            }

            QLineEdit {
                background: #0B1220;
                border: 1px solid #374151;
                border-radius: 8px;
                padding: 8px;
                color: #E5E7EB;
            }

            QCheckBox {
                color: #D1D5DB;
                padding: 8px;
            }
            """
        )

    def refresh(self):
        self.cfg = load_config()
        self.printer_list.clear()

        try:
            infos = get_printer_infos(self.cfg)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось получить список принтеров:\n{e}")
            return

        current = next((p for p in infos if p.is_default), None)
        self.current_label.setText(f"Текущий принтер: {current.display_name if current else 'не найден'}")

        for p in infos:
            if not p.is_known and self.cfg.get("hide_unknown_printers_for_users", False):
                continue

            item = QListWidgetItem(self.format_printer_item(p))
            item.setData(Qt.UserRole, p.system_name)
            self.printer_list.addItem(item)

    def format_printer_item(self, p: PrinterInfo) -> str:
        marker = "✓ " if p.is_default else "   "
        unknown = "  · новый" if not p.is_known else ""
        return f"{marker}{p.display_name}{unknown}"

    def selected_system_name(self) -> Optional[str]:
        current = self.printer_list.currentItem()
        if current:
            return current.data(Qt.UserRole)
        return None

    def set_selected_printer(self):
        system_name = self.selected_system_name()

        if not system_name:
            QMessageBox.information(self, "Принтер", "Выберите принтер из списка.")
            return

        try:
            set_windows_default_printer(system_name)
            patched = patch_browser_printer_preferences(system_name, self.cfg)
            log(f"Default printer changed to {system_name}. Browser profiles patched: {patched}")

            QMessageBox.information(
                self,
                "Готово",
                f"Принтер установлен по умолчанию.\n\n"
                f"Браузерных профилей обновлено: {patched}\n\n"
                f"Если браузер был открыт, закройте и откройте его заново."
            )

            self.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сменить принтер:\n{e}")

    def open_admin(self):
        dlg = PinDialog(self)

        if dlg.exec() != QDialog.Accepted:
            return

        self.cfg = load_config()

        if dlg.pin != str(self.cfg.get("admin_pin", "2468")):
            QMessageBox.warning(self, "PIN", "Неверный PIN.")
            return

        admin = AdminDialog(self.cfg, self)
        admin.exec()
        self.refresh()


def main():
    ensure_app_dir()

    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
