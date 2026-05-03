import re

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QListWidget,
    QDialogButtonBox, QLabel, QMessageBox, QInputDialog,
    QCheckBox, QSpinBox, QFileDialog, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor

import stb

_FIELD_STYLE = """
    QLineEdit {
        background: #252525;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        padding: 5px 8px;
        color: #ddd;
        font-size: 13px;
    }
    QLineEdit:focus { border-color: #0078d4; }
"""

_LIST_STYLE = """
    QListWidget {
        background: #1a1a1a;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        color: #ddd;
        font-size: 13px;
    }
    QListWidget::item { padding: 5px 10px; }
    QListWidget::item:selected { background: #0078d4; color: white; }
"""

_BTN_SMALL = """
    QPushButton {
        background: #2e2e2e;
        color: #ccc;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 5px 12px;
        font-size: 12px;
    }
    QPushButton:hover { background: #3a3a3a; }
"""

_BTN_TEST = """
    QPushButton {
        background: #1a3a1a;
        color: #4caf50;
        border: 1px solid #4caf50;
        border-radius: 4px;
        padding: 5px 14px;
        font-size: 12px;
    }
    QPushButton:hover { background: #234a23; }
    QPushButton:disabled { background: #2a2a2a; color: #555; border-color: #444; }
"""


class PortalDialog(QDialog):
    def __init__(self, portal=None, parent=None):
        super().__init__(parent)
        self._portal = portal
        self.setWindowTitle("Edit Portal" if portal else "Add Portal")
        self.setMinimumWidth(460)
        self.setStyleSheet("background: #1e1e1e; color: #ddd;")
        self._setup_ui()
        if portal:
            self._populate(portal)

    # ------------------------------------------------------------------ UI ---

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My IPTV Provider")
        self.name_edit.setStyleSheet(_FIELD_STYLE)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://provider.com:8080")
        self.url_edit.setStyleSheet(_FIELD_STYLE)

        self.proxy_edit = QLineEdit()
        self.proxy_edit.setPlaceholderText("http://proxy:8080  (optional)")
        self.proxy_edit.setStyleSheet(_FIELD_STYLE)

        self.try_all_macs = QCheckBox("Try all MACs on stream failure")
        self.try_all_macs.setChecked(True)

        epg_row = QHBoxLayout()
        self.epg_offset = QSpinBox()
        self.epg_offset.setRange(-12, 12)
        self.epg_offset.setSuffix(" h")
        self.epg_offset.setStyleSheet(
            "background: #252525; color: #ddd; border: 1px solid #3a3a3a; "
            "border-radius: 4px; padding: 3px 6px;"
        )
        epg_row.addWidget(self.epg_offset)
        epg_row.addStretch()

        form.addRow("Name:", self.name_edit)
        form.addRow("Portal URL:", self.url_edit)
        form.addRow("Proxy:", self.proxy_edit)
        form.addRow("Options:", self.try_all_macs)
        form.addRow("EPG Offset:", epg_row)
        layout.addLayout(form)

        # MAC section
        mac_header = QLabel("MAC Addresses")
        mac_header.setStyleSheet("font-size: 12px; color: #aaa; font-weight: bold;")
        layout.addWidget(mac_header)

        self.mac_list = QListWidget()
        self.mac_list.setFixedHeight(110)
        self.mac_list.setStyleSheet(_LIST_STYLE)
        layout.addWidget(self.mac_list)

        mac_btns = QHBoxLayout()
        mac_btns.setSpacing(6)

        btn_add = QPushButton("Add MAC")
        btn_add.setStyleSheet(_BTN_SMALL)
        btn_add.clicked.connect(self._add_mac)

        btn_remove = QPushButton("Remove")
        btn_remove.setStyleSheet(_BTN_SMALL)
        btn_remove.clicked.connect(self._remove_mac)

        btn_import = QPushButton("Import TXT")
        btn_import.setStyleSheet(_BTN_SMALL)
        btn_import.clicked.connect(self._import_txt)

        self.btn_test = QPushButton("Test Connection")
        self.btn_test.setStyleSheet(_BTN_TEST)
        self.btn_test.clicked.connect(self._test_connection)

        mac_btns.addWidget(btn_add)
        mac_btns.addWidget(btn_remove)
        mac_btns.addWidget(btn_import)
        mac_btns.addStretch()
        mac_btns.addWidget(self.btn_test)
        layout.addLayout(mac_btns)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; color: #888;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setStyleSheet(
            "background: #0078d4; color: white; border: none; "
            "border-radius: 4px; padding: 6px 18px;"
        )
        buttons.button(QDialogButtonBox.Cancel).setStyleSheet(_BTN_SMALL)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, portal):
        self.name_edit.setText(portal.name)
        self.url_edit.setText(portal.url)
        self.proxy_edit.setText(portal.proxy)
        self.try_all_macs.setChecked(portal.try_all_macs)
        self.epg_offset.setValue(portal.epg_offset)
        for mac in portal.macs:
            self.mac_list.addItem(mac)

    # ---------------------------------------------------------------- Slots ---

    def _add_mac(self):
        mac, ok = QInputDialog.getText(
            self,
            "Add MAC Address",
            "Enter MAC address (e.g. AA:BB:CC:DD:EE:FF):",
        )
        if ok and mac.strip():
            self.mac_list.addItem(mac.strip().upper())

    def _remove_mac(self):
        row = self.mac_list.currentRow()
        if row >= 0:
            self.mac_list.takeItem(row)

    def _import_txt(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import TXT", "", "Text files (*.txt);;All files (*)"
        )
        if not paths:
            return

        url_pattern = re.compile(r'http://[^\s\r\n]+/c/', re.IGNORECASE)
        mac_pattern = re.compile(r'[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}')

        found_urls: list[str] = []
        found_macs: list[str] = []

        for path in paths:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
                found_urls.extend(url_pattern.findall(text))
                found_macs.extend(mac_pattern.findall(text))
            except Exception as e:
                QMessageBox.warning(self, "Import TXT", f"Could not read {path}:\n{e}")

        # Fill URL field with first match if currently empty
        if found_urls and not self.url_edit.text().strip():
            self.url_edit.setText(found_urls[0])

        # Add MACs — skip duplicates already in the list
        existing = {self.mac_list.item(i).text().upper() for i in range(self.mac_list.count())}
        added = 0
        for mac in found_macs:
            mac_upper = mac.upper()
            if mac_upper not in existing:
                self.mac_list.addItem(mac_upper)
                existing.add(mac_upper)
                added += 1

        self.status_label.setText(
            f"Imported {added} MAC(s)" + (f" · URL: {found_urls[0]}" if found_urls and added == 0 else "")
            if found_urls or added else "No URLs or MACs found in selected file(s)."
        )
        self.status_label.setStyleSheet("font-size: 11px; color: #888;")

    def _test_connection(self):
        url = self.url_edit.text().strip()
        proxy = self.proxy_edit.text().strip() or None
        macs = [self.mac_list.item(i).text() for i in range(self.mac_list.count())]

        if not url:
            QMessageBox.warning(self, "Test", "Please enter a portal URL first.")
            return
        if not macs:
            QMessageBox.warning(self, "Test", "Please add at least one MAC address.")
            return

        self.btn_test.setEnabled(False)
        self.status_label.setText("Discovering portal URL…")
        self.status_label.setStyleSheet("font-size: 11px; color: #888;")
        QApplication.processEvents()

        portal_url = stb.getUrl(url, proxy)
        if not portal_url:
            self.status_label.setText("Could not discover portal URL.")
            self.status_label.setStyleSheet("font-size: 11px; color: #f44336;")
            self.btn_test.setEnabled(True)
            return

        valid: list[str] = []
        invalid: list[str] = []

        for i, mac in enumerate(macs):
            item = self.mac_list.item(i)
            self.status_label.setText(f"Testing {mac}…")
            item.setForeground(QBrush(QColor("#888")))
            item.setText(mac)
            QApplication.processEvents()

            try:
                token = stb.getToken(portal_url, mac, proxy)
                if not token:
                    raise Exception("No token returned")
                stb.getProfile(portal_url, mac, token, proxy)
                expires = stb.getExpires(portal_url, mac, token, proxy)
                label = f"✓  {mac}"
                if expires:
                    label += f"   [{expires}]"
                item.setText(label)
                item.setForeground(QBrush(QColor("#4caf50")))
                valid.append(mac)
            except Exception:
                item.setText(f"✗  {mac}")
                item.setForeground(QBrush(QColor("#f44336")))
                invalid.append(mac)

        if invalid:
            reply = QMessageBox.question(
                self, "Test Complete",
                f"{len(valid)} valid · {len(invalid)} invalid MAC(s) found.\n\n"
                "Remove invalid MAC addresses?\n\n"
                + "\n".join(f"  • {m}" for m in invalid),
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.mac_list.clear()
                for mac in valid:
                    self.mac_list.addItem(mac)
                self.status_label.setText(
                    f"Removed {len(invalid)} MAC(s). {len(valid)} valid remaining."
                )
                self.status_label.setStyleSheet("font-size: 11px; color: #888;")
                self.btn_test.setEnabled(True)
                return

        # Restore clean display (without ✓/✗ markers)
        self.mac_list.clear()
        for mac in macs:
            self.mac_list.addItem(mac)

        if not invalid:
            self.status_label.setText(f"All {len(valid)} MAC(s) are valid.")
            self.status_label.setStyleSheet("font-size: 11px; color: #4caf50;")
        else:
            self.status_label.setText(f"{len(valid)} valid · {len(invalid)} invalid MAC(s).")
            self.status_label.setStyleSheet("font-size: 11px; color: #888;")

        self.btn_test.setEnabled(True)

    def _on_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Please enter a portal name.")
            return
        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Please enter a portal URL.")
            return
        if self.mac_list.count() == 0:
            QMessageBox.warning(self, "Validation", "Please add at least one MAC address.")
            return
        self.accept()

    # --------------------------------------------------------------- Result ---

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "url": self.url_edit.text().strip(),
            "macs": [self.mac_list.item(i).text() for i in range(self.mac_list.count())],
            "proxy": self.proxy_edit.text().strip(),
            "try_all_macs": self.try_all_macs.isChecked(),
            "epg_offset": self.epg_offset.value(),
        }
