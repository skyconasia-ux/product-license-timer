"""
Main application window with left sidebar navigation.
Accepts UserSession and db_session from login.
"""
from __future__ import annotations
import shutil
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QMessageBox, QToolBar,
    QSystemTrayIcon, QMenu, QFileDialog,
    QLabel, QStatusBar, QPushButton, QFrame, QStackedWidget,
)
from sqlalchemy.orm import Session

from services.auth_service import UserSession
from services.notification_service import check_and_send_v2, get_smtp_config
from services.product_service import (
    add_product, update_product, delete_product,
    get_product, get_all_products, get_my_products, delete_expired_products,
)
from services.timer_service import TimerService
from ui.product_form import ProductForm
from ui.product_table import ProductTable
from ui.settings_dialog import SettingsDialog
from utils.csv_exporter import export_to_csv


class MainWindow(QMainWindow):
    def __init__(
        self,
        user_session: UserSession,
        db_session: Session,
    ):
        super().__init__()
        self._user = user_session
        self._session = db_session
        self._show_my_products = False
        self.setWindowTitle("Product License Timer")
        self.setMinimumSize(1200, 680)

        self._timer = TimerService(self)
        self._timer.tick.connect(self._on_tick)

        self._build_ui()
        self._build_tray()
        self._on_tick()
        self._timer.start()

    # ---------------------------------------------------------------- Build UI

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        h_layout = QHBoxLayout(root)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        h_layout.addWidget(self._build_sidebar())

        content = QWidget()
        v_layout = QVBoxLayout(content)
        v_layout.setContentsMargins(4, 4, 4, 4)

        self._stack = QStackedWidget()
        self._products_widget = self._build_products_page()
        self._stack.addWidget(self._products_widget)  # index 0

        if self._user.role in ("admin", "superadmin"):
            from ui.contacts_page import ContactsPage
            from ui.recipients_page import RecipientsPage
            self._contacts_widget = ContactsPage(self._session, self._user)
            self._recipients_widget = RecipientsPage(self._session, self._user)
            self._stack.addWidget(self._contacts_widget)   # index 1
            self._stack.addWidget(self._recipients_widget) # index 2

        self._stack.setCurrentIndex(0)
        v_layout.addWidget(self._stack)

        self._status_label = QLabel()
        status_bar = QStatusBar()
        status_bar.addWidget(self._status_label)
        self.setStatusBar(status_bar)

        self._build_menu()
        h_layout.addWidget(content, stretch=1)

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setFixedWidth(160)
        sidebar.setStyleSheet("""
            QFrame { background: #1e293b; }
            QPushButton {
                text-align: left; padding: 10px 16px; border: none;
                color: #94a3b8; font-size: 13px; background: transparent;
            }
            QPushButton:hover { background: #334155; color: #e2e8f0; }
            QPushButton[active="true"] { background: #3b82f6; color: white; }
        """)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(2)

        title = QLabel("License Timer")
        title.setStyleSheet("color: #e2e8f0; font-weight: bold; padding: 8px 16px 16px;")
        layout.addWidget(title)

        self._nav_products = QPushButton("📋  Products")
        self._nav_products.setProperty("active", "true")
        self._nav_products.clicked.connect(lambda: self._nav_to(0, self._nav_products))
        layout.addWidget(self._nav_products)

        self._nav_contacts = None
        self._nav_recipients = None

        if self._user.role in ("admin", "superadmin"):
            self._nav_contacts = QPushButton("👤  Contacts")
            self._nav_contacts.clicked.connect(lambda: self._nav_to(1, self._nav_contacts))
            self._nav_recipients = QPushButton("📧  Recipients")
            self._nav_recipients.clicked.connect(lambda: self._nav_to(2, self._nav_recipients))
            layout.addWidget(self._nav_contacts)
            layout.addWidget(self._nav_recipients)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #334155;")
        layout.addWidget(sep)

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn)

        user_label = QLabel(self._user.email)
        user_label.setStyleSheet(
            "color: #64748b; font-size: 10px; padding: 8px 16px; word-wrap: break-word;"
        )
        user_label.setWordWrap(True)
        layout.addWidget(user_label)

        return sidebar

    def _nav_to(self, index: int, btn: QPushButton) -> None:
        self._stack.setCurrentIndex(index)
        for b in [self._nav_products, self._nav_contacts, self._nav_recipients]:
            if b:
                b.setProperty("active", "false")
                b.style().unpolish(b)
                b.style().polish(b)
        btn.setProperty("active", "true")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def _build_products_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self._table = ProductTable()
        self._table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self._build_products_toolbar())
        layout.addWidget(self._table)
        return w

    def _build_products_toolbar(self) -> QToolBar:
        tb = QToolBar("Products")
        tb.setMovable(False)

        def act(label, slot):
            a = QAction(label, self)
            a.triggered.connect(slot)
            return a

        tb.addAction(act("+ Add", self._add_product))
        tb.addAction(act("✏ Edit", self._edit_product))
        tb.addAction(act("🗑 Delete", self._delete_product))
        tb.addSeparator()
        tb.addAction(act("Clear Expired", self._clear_expired))
        tb.addAction(act("⟳ Check Now", self._timer.force_tick))
        tb.addSeparator()

        self._filter_btn = QPushButton("My Products")
        self._filter_btn.setCheckable(True)
        self._filter_btn.toggled.connect(self._toggle_filter)
        tb.addWidget(self._filter_btn)
        tb.addSeparator()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search name / customer / order...")
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._table.apply_filter)
        tb.addWidget(self._search)
        return tb

    def _toggle_filter(self, checked: bool) -> None:
        self._show_my_products = checked
        self._filter_btn.setText("My Products ✓" if checked else "My Products")
        self._on_tick()

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
        menu.addAction("⟳ Check Now", self._timer.force_tick)
        menu.addSeparator()
        menu.addAction("Exit", self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # --------------------------------------------------------------- Events

    def closeEvent(self, event) -> None:
        self._quit_app()
        event.ignore()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            self.hide()
            self._tray.showMessage(
                "Product License Timer", "Running in the background.",
                QSystemTrayIcon.MessageIcon.Information, 2000,
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
        self._session.close()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # ------------------------------------------------------------------ Tick

    def _on_tick(self) -> None:
        if self._show_my_products:
            products = get_my_products(self._session, self._user)
        else:
            products = get_all_products(self._session)

        # Enrich with contact names for display
        enriched = self._enrich_products(products)
        self._table.refresh(enriched)
        check_and_send_v2(products, self._session, get_smtp_config())
        self._status_label.setText(
            f"Last checked: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}  |  "
            f"{len(products)} product(s) tracked  |  {self._user.email}"
        )

    def _enrich_products(self, products: list) -> list[dict]:
        """Convert ORM products to dicts with resolved contact names."""
        from models.orm import Contact
        result = []
        for p in products:
            d = {
                "id": p.id,
                "name": p.product_name,
                "product_name": p.product_name,
                "customer_name": p.customer_name,
                "order_number": p.order_number,
                "start_date": p.start_date,
                "duration_days": p.duration_days,
                "expiry_date": p.expiry_date,
                "notes": p.notes,
                "consultant_name": None,
                "account_manager_name": None,
                "project_manager_name": None,
            }
            for key, fk in [
                ("consultant_name", p.consultant_id),
                ("account_manager_name", p.account_manager_id),
                ("project_manager_name", p.project_manager_id),
            ]:
                if fk:
                    c = self._session.get(Contact, fk)
                    d[key] = c.name if c else None
            result.append(d)
        return result

    # ------------------------------------------------------------- Product CRUD

    def _add_product(self) -> None:
        dlg = ProductForm(self, session=self._session, caller=self._user)
        if dlg.exec():
            data = dlg.get_data()
            try:
                add_product(self._session, self._user, **data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not add product:\n{e}")

    def _edit_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to edit.")
            return
        product = get_product(self._session, pid)
        dlg = ProductForm(self, product=product, session=self._session, caller=self._user)
        if dlg.exec():
            data = dlg.get_data()
            try:
                update_product(self._session, self._user, pid, **data)
                self._on_tick()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update product:\n{e}")

    def _delete_product(self) -> None:
        pid = self._table.get_selected_product_id()
        if pid is None:
            QMessageBox.information(self, "No Selection", "Please select a product to delete.")
            return
        product = get_product(self._session, pid)
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete '{product.product_name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_product(self._session, pid)
            self._on_tick()

    def _clear_expired(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Expired",
            "Remove all expired products? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count = delete_expired_products(self._session)
            self._on_tick()
            QMessageBox.information(self, "Done", f"Removed {count} expired product(s).")

    # --------------------------------------------------------------- Extras

    def _export_csv(self) -> None:
        if self._show_my_products:
            products = get_my_products(self._session, self._user)
        else:
            products = get_all_products(self._session)
        enriched = self._enrich_products(products)
        export_to_csv(enriched, self)

    def _backup_db(self) -> None:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default = str(Path.home() / f"licenses_backup_{ts}.db")
        path, _ = QFileDialog.getSaveFileName(
            self, "Backup Database", default, "SQLite DB (*.db)"
        )
        if path:
            from models.database import DB_PATH
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
            "Product License Timer — Phase 2\n\n"
            "Multi-user centralized license tracker.\n"
            "Built with Python 3.13 + PyQt6 + SQLAlchemy",
        )
