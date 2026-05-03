import uuid

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QFrame, QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from config import Config, Portal
from ui.portal_dialog import PortalDialog

_LIST_STYLE = """
    QListWidget {
        background: #1e1e1e;
        border: 1px solid #3a3a3a;
        border-radius: 6px;
        color: #ddd;
        outline: none;
    }
    QListWidget::item {
        padding: 10px 14px;
        border-bottom: 1px solid #2a2a2a;
    }
    QListWidget::item:selected {
        background: #0078d4;
        color: white;
        border-bottom-color: #0060aa;
    }
    QListWidget::item:hover:!selected { background: #272727; }
"""

_BTN = """
    QPushButton {
        background: #2a2a2a;
        color: #ccc;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        padding: 7px 0;
        font-size: 13px;
    }
    QPushButton:hover { background: #363636; }
    QPushButton:disabled { color: #555; background: #222; border-color: #2a2a2a; }
"""

_BTN_PRIMARY = """
    QPushButton {
        background: #0078d4;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 7px 0;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover { background: #006bbf; }
"""

_BTN_DANGER = """
    QPushButton {
        background: #2a1010;
        color: #f08080;
        border: 1px solid #7a2020;
        border-radius: 4px;
        padding: 7px 0;
        font-size: 13px;
    }
    QPushButton:hover { background: #c0392b; color: white; border-color: #c0392b; }
    QPushButton:disabled { background: #222; color: #555; border-color: #2a2a2a; }
"""


class PortalManagerDialog(QDialog):
    portals_changed = Signal()

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Portal Manager")
        self.setMinimumSize(620, 440)
        self.resize(680, 500)
        self.setStyleSheet("background: #1a1a1a; color: #ddd;")
        self._build_ui()
        self._populate()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(6)

        header = QLabel("PORTALS")
        header.setStyleSheet("color: #666; font-size: 10px; font-weight: bold; letter-spacing: 1.5px;")
        left.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(_LIST_STYLE)
        self.list_widget.itemDoubleClicked.connect(self._edit)
        self.list_widget.currentRowChanged.connect(self._refresh_buttons)
        left.addWidget(self.list_widget)
        root.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(6)

        self.btn_add    = self._make_btn("Add Portal",    _BTN_PRIMARY)
        self.btn_edit   = self._make_btn("Edit",          _BTN)
        self.btn_remove = self._make_btn("Remove",        _BTN_DANGER)

        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet("QFrame { background: #2e2e2e; border: none; }")

        self.btn_up   = self._make_btn("▲  Move Up",   _BTN)
        self.btn_down = self._make_btn("▼  Move Down", _BTN)

        self.btn_add.clicked.connect(self._add)
        self.btn_edit.clicked.connect(self._edit)
        self.btn_remove.clicked.connect(self._remove)
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down.clicked.connect(self._move_down)

        right.addWidget(self.btn_add)
        right.addWidget(self.btn_edit)
        right.addWidget(self.btn_remove)
        right.addSpacing(4)
        right.addWidget(div)
        right.addSpacing(4)
        right.addWidget(self.btn_up)
        right.addWidget(self.btn_down)
        right.addStretch()

        root.addLayout(right)
        self._refresh_buttons(-1)

    @staticmethod
    def _make_btn(label: str, style: str) -> QPushButton:
        b = QPushButton(label)
        b.setFixedWidth(130)
        b.setStyleSheet(style)
        return b

    def _populate(self, select_id: str = None):
        self.list_widget.clear()
        for portal in self.config.portals:
            count = len(portal.macs)
            mac_str = f"{count} MAC{'s' if count != 1 else ''}"
            item = QListWidgetItem(f"{portal.name}\n{portal.url}  •  {mac_str}")
            item.setData(Qt.UserRole, portal.id)
            self.list_widget.addItem(item)

        if select_id:
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).data(Qt.UserRole) == select_id:
                    self.list_widget.setCurrentRow(i)
                    return
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _refresh_buttons(self, row: int):
        has   = row >= 0
        count = self.list_widget.count()
        self.btn_edit.setEnabled(has)
        self.btn_remove.setEnabled(has)
        self.btn_up.setEnabled(has and row > 0)
        self.btn_down.setEnabled(has and row < count - 1)

    def _selected_portal(self):
        item = self.list_widget.currentItem()
        return self.config.get_portal(item.data(Qt.UserRole)) if item else None

    def _add(self):
        dlg = PortalDialog(parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data   = dlg.get_data()
        portal = Portal(
            name=data["name"], url=data["url"], macs=data["macs"],
            proxy=data["proxy"], epg_offset=data["epg_offset"],
            try_all_macs=data["try_all_macs"],
        )
        self.config.add_portal(portal)
        self._populate(select_id=portal.id)
        self.portals_changed.emit()

    def _edit(self):
        portal = self._selected_portal()
        if not portal:
            return
        dlg = PortalDialog(portal=portal, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        data = dlg.get_data()
        portal.name        = data["name"]
        portal.url         = data["url"]
        portal.macs        = data["macs"]
        portal.proxy       = data["proxy"]
        portal.epg_offset  = data["epg_offset"]
        portal.try_all_macs = data["try_all_macs"]
        self.config.update_portal(portal)
        self._populate(select_id=portal.id)
        self.portals_changed.emit()

    def _remove(self):
        portal = self._selected_portal()
        if not portal:
            return
        if QMessageBox.question(
            self, "Remove Portal", f"Remove '{portal.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self.config.remove_portal(portal.id)
        self._populate()
        self.portals_changed.emit()

    def _move_up(self):
        row = self.list_widget.currentRow()
        if row <= 0:
            return
        p = self.config.portals
        p[row - 1], p[row] = p[row], p[row - 1]
        self.config.save()
        self._populate(select_id=p[row - 1].id)
        self.portals_changed.emit()

    def _move_down(self):
        row = self.list_widget.currentRow()
        p   = self.config.portals
        if row < 0 or row >= len(p) - 1:
            return
        p[row], p[row + 1] = p[row + 1], p[row]
        self.config.save()
        self._populate(select_id=p[row + 1].id)
        self.portals_changed.emit()
