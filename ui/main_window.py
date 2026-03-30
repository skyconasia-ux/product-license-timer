"""
Main application window. Wires all components together.
Single responsibility: application shell -- layout, menus, toolbar, tray, event routing.
"""
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QLineEdit, QMessageBox, QToolBar,
    QSystemTrayIcon, QMenu, QFileDialog,
    QLabel, QStatusBar,
)

from models.database import DB_PATH
from services.database_service import DatabaseService
from services.notification_service import NotificationService
from services.timer_service import TimerService
from ui.product_form import ProductForm
from ui.product_table import ProductTable
from ui.settings_dialog import SettingsDialog
from utils.csv_exporter import export_to_csv


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Product License Timer")
        self.setMinimumSize(1100, 620)

        self._db = DatabaseService()
        self._notifier = NotificationService()
        self._timer = TimerService(self)
        self._timer.tick.connect(self._on_tick)

        self._build_ui()
        self._build_tray()
        self._on_tick()       # populate immediately on launch
        self._timer.start()

    # ---------------------------------------------------------------- Build UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        # Table must be created before toolbar (toolbar connects to table signals)
        self._table = ProductTable()
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        self.addToolBar(self._build_toolbar())

        layout.addWidget(self._table)

        self._status_label = QLabel()
        status_bar = QStatusBar()
        status_bar.addWidget(self._status_label)
        self.setStatusBar(status_bar)

        self._build_menu()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar("Main")
        tb.setMovable(False)

        def act(label, slot):
            a = QAction(label, self)
            a.triggered.connect(slot)
            return a

        tb.addAction(act("+ Add", self._add_product))
        tb.addAction(act("\u270f Edit", self._edit_product))
        tb.addAction(act("\U0001f5d1 Delete", self._delete_product))
        tb.addSeparator()
        tb.addAction(act("Clear Expired", self._clear_expired))
        tb.addAction(act("\u27f3 Check Now", self._timer.force_tick))
        tb.addSeparator()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name / customer / order...")
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._table.apply_filter)
        tb.addWidget(self._search)
        return tb

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_m = mb.addMenu("File")
        file_m.addAction("Export CSV", self._export_csv)
        file_m.addAction("Backup Database", self._backup_db)
        file_m.addSeparator()
        file_m.addAction("Exit", self._quit_app)

        edit_m = mb.addMenu("Edit")
        edit_m.addAction("Add Product", self._add_product)
        edit_m.addAction("Edit Product", self._edit_product)
        edit_m.addAction("Delete Product", self._delete_product)
        edit_m.addSeparator()
        edit_m.addAction("Clear Expired", self._clear_expired)

        settings_m = mb.addMenu("Settings")
        settings_m.addAction("Timer / Email / System", self._open_settings)

        help_m = mb.addMenu("Help")
        help_m.addAction("About", self._about)

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
        )
        self._tray.setToolTip("Product License Timer")

        menu = QMenu()
        menu.addAction("Open", self._show_window)
        menu.addAction("\u27f3 Check Now", self._timer.force_tick)
        menu.addSeparator()
        menu.addAction("Exit", self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # --------------------------------------------------------------- Events

    def closeEvent(self, event) -> None:
        """X button -> quit the application."""
        self._quit_app()
        event.ignore()

    def changeEvent(self, event) -> None:
        """Minimize button -> hide to tray."""
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self._tray.showMessage(
                "Product License Timer",
                "Running in the background. Right-click the tray icon to open.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        super().changeEvent(event)

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Edit", self._edit_product)
        menu.addAction("Delete", self._delete_product)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_app(self) -> None:
        self._timer.stop()
        self._tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # ------------------------------------------------------------------ Tick

    def _on_tick(self) -> None:
        products = self._db.get_all_products()
        self._table.refresh(products)
        self._notifier.check_and_send(products, self._db)
        self._status_label.setText(
            f"Last checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  "
            f"{len(products)} product(s) tracked"
        )

    # ------------------------------------------------------------- Product CRUD

    def _add_product(self) -> None:
        dlg = ProductForm(self)
        if dlg.exec():
            data = dlg.get_data()
            try:
                self._db.add_product(**data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add product:\n{e}")

    def _edit_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to edit.")
            return
        product = self._db.get_product(pid)
        dlg = ProductForm(self, product=product)
        if dlg.exec():
            data = dlg.get_data()
            try:
                self._db.update_product(pid, **data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update product:\n{e}")

    def _delete_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to delete.")
            return
        product = self._db.get_product(pid)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{product['name']}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._db.delete_product(pid)
            self._on_tick()

    def _clear_expired(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Expired",
            "Remove all expired products from the database?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = self._db.delete_expired_products()
            self._on_tick()
            QMessageBox.information(self, "Done", f"Removed {count} expired product(s).")

    # --------------------------------------------------------------- Extras

    def _export_csv(self) -> None:
        products = self._db.get_all_products()
        export_to_csv(products, self)

    def _backup_db(self) -> None:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default = str(Path.home() / f"licenses_backup_{ts}.db")
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", default, "SQLite DB (*.db)"
        )
        if path:
            shutil.copy2(str(DB_PATH), path)
            QMessageBox.information(self, "Backup Complete", f"Saved to:\n{path}")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            cfg = dlg.get_app_config()
            self._timer.set_interval(cfg["timer_interval_seconds"])

    def _about(self) -> None:
        QMessageBox.about(
            self, "About Product License Timer",
            "Product License Timer\n\n"
            "Tracks trial software license expiry dates.\n"
            "Sends email alerts at 15, 10, and 5 day thresholds.\n\n"
            "Built with Python 3.13 + PyQt6",
        )
