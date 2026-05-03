import uuid
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout,
    QSplitter, QStatusBar, QToolBar,
    QComboBox, QLabel, QPushButton, QMessageBox,
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt

from config import Config, Portal
from worker import ChannelLoader, StreamResolver, EPGLoader
from ui.channel_panel import ChannelPanel
from ui.player_widget import PlayerWidget
from ui.epg_widget import EPGWidget
from ui.portal_dialog import PortalDialog

_TOOLBAR_STYLE = """
    QToolBar {
        background: #161616;
        border-bottom: 1px solid #2a2a2a;
        padding: 4px 8px;
        spacing: 6px;
    }
"""

_COMBO_STYLE = """
    QComboBox {
        background: #272727;
        color: #ddd;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        padding: 5px 10px;
        min-width: 180px;
        font-size: 13px;
    }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox QAbstractItemView {
        background: #272727;
        color: #ddd;
        selection-background-color: #0078d4;
        border: 1px solid #3a3a3a;
    }
"""

_BTN_PRIMARY = """
    QPushButton {
        background: #0078d4;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
        font-size: 13px;
    }
    QPushButton:hover { background: #006bbf; }
    QPushButton:disabled { background: #333; color: #666; }
"""

_BTN_SECONDARY = """
    QPushButton {
        background: #2a2a2a;
        color: #ccc;
        border: 1px solid #444;
        border-radius: 4px;
        padding: 6px 14px;
        font-size: 13px;
    }
    QPushButton:hover { background: #363636; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = Config()
        self._channel_loader: ChannelLoader | None = None
        self._stream_resolver: StreamResolver | None = None
        self._epg_loader: EPGLoader | None = None
        self._current_channel: dict | None = None
        self._tried_macs: set = set()
        self._is_fullscreen: bool = False

        self.setWindowTitle("MacPlayer")
        self.setMinimumSize(1000, 600)
        self.resize(1280, 740)

        self._build_central()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._refresh_portal_combo()

        self.player.set_volume(self.config.volume)

    # ------------------------------------------------------------------ UI ---

    def _build_central(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(2)
        self.splitter.setStyleSheet("QSplitter::handle { background: #2a2a2a; }")

        self.channel_panel = ChannelPanel()
        self.channel_panel.channel_selected.connect(self._on_channel_selected)

        self.player = PlayerWidget()
        self.player.playback_failed.connect(self._on_playback_failed)
        self.player.fullscreen_requested.connect(self._toggle_fullscreen)

        self.epg_widget = EPGWidget()

        self.splitter.addWidget(self.channel_panel)
        self.splitter.addWidget(self.player)
        self.splitter.addWidget(self.epg_widget)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([240, 800, 240])

        layout.addWidget(self.splitter)

    def _build_menu(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        file_menu.addAction("Exit", self.close)

        portals_menu = mb.addMenu("Portals")
        portals_menu.addAction("Add Portal…", self._add_portal)
        portals_menu.addAction("Edit Portal…", self._edit_portal)
        portals_menu.addAction("Remove Portal", self._remove_portal)
        portals_menu.addSeparator()
        portals_menu.addAction("Reload Channels", self._load_channels)

        view_menu = mb.addMenu("View")
        self.act_epg = QAction("EPG Panel", self, checkable=True, checked=True)
        self.act_epg.triggered.connect(
            lambda checked: self.epg_widget.setVisible(checked)
        )
        view_menu.addAction(self.act_epg)

        help_menu = mb.addMenu("Help")
        help_menu.addAction("About MacPlayer", self._about)

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setStyleSheet(_TOOLBAR_STYLE)
        self.addToolBar(tb)

        portal_lbl = QLabel("  Portal: ")
        portal_lbl.setStyleSheet("color: #888; font-size: 12px;")
        tb.addWidget(portal_lbl)

        self.portal_combo = QComboBox()
        self.portal_combo.setStyleSheet(_COMBO_STYLE)
        self.portal_combo.currentIndexChanged.connect(self._on_portal_changed)
        tb.addWidget(self.portal_combo)

        tb.addSeparator()

        self.btn_load = QPushButton("Load Channels")
        self.btn_load.setStyleSheet(_BTN_PRIMARY)
        self.btn_load.clicked.connect(self._load_channels)
        tb.addWidget(self.btn_load)

        tb.addSeparator()

        btn_add = QPushButton("+ Add Portal")
        btn_add.setStyleSheet(_BTN_SECONDARY)
        btn_add.clicked.connect(self._add_portal)
        tb.addWidget(btn_add)

    def _build_statusbar(self):
        sb = QStatusBar()
        sb.setStyleSheet(
            "QStatusBar { background: #141414; color: #666; border-top: 1px solid #2a2a2a; }"
        )
        self.setStatusBar(sb)
        sb.showMessage("Ready — add a portal to get started")

    # -------------------------------------------------------- Portal combo ---

    def _refresh_portal_combo(self):
        self.portal_combo.blockSignals(True)
        self.portal_combo.clear()
        for p in self.config.portals:
            self.portal_combo.addItem(p.name, p.id)
        self.portal_combo.blockSignals(False)

        has = bool(self.config.portals)
        self.btn_load.setEnabled(has)
        if not has:
            self.statusBar().showMessage("No portals configured — click '+ Add Portal' to begin")

    def _on_portal_changed(self, _index: int):
        self.channel_panel.clear()
        self.player.stop()
        self.epg_widget.clear()

    # ----------------------------------------------------------- Portal CRUD ---

    def _add_portal(self):
        dlg = PortalDialog(parent=self)
        if dlg.exec() == PortalDialog.Accepted:
            data = dlg.get_data()
            portal = Portal(
                id=str(uuid.uuid4())[:8],
                name=data["name"],
                url=data["url"],
                macs=data["macs"],
                proxy=data["proxy"],
                epg_offset=data["epg_offset"],
                try_all_macs=data["try_all_macs"],
            )
            self.config.add_portal(portal)
            self._refresh_portal_combo()
            idx = self.portal_combo.findData(portal.id)
            if idx >= 0:
                self.portal_combo.setCurrentIndex(idx)

    def _edit_portal(self):
        portal_id = self.portal_combo.currentData()
        if not portal_id:
            QMessageBox.information(self, "Edit Portal", "No portal selected.")
            return
        portal = self.config.get_portal(portal_id)
        if not portal:
            return
        dlg = PortalDialog(portal=portal, parent=self)
        if dlg.exec() == PortalDialog.Accepted:
            data = dlg.get_data()
            portal.name = data["name"]
            portal.url = data["url"]
            portal.macs = data["macs"]
            portal.proxy = data["proxy"]
            portal.epg_offset = data["epg_offset"]
            portal.try_all_macs = data["try_all_macs"]
            self.config.update_portal(portal)
            self._refresh_portal_combo()

    def _remove_portal(self):
        portal_id = self.portal_combo.currentData()
        if not portal_id:
            return
        portal = self.config.get_portal(portal_id)
        if not portal:
            return
        reply = QMessageBox.question(
            self, "Remove Portal",
            f"Remove portal '{portal.name}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.config.remove_portal(portal_id)
            self.channel_panel.clear()
            self.player.stop()
            self.epg_widget.clear()
            self._refresh_portal_combo()

    # ------------------------------------------------------ Channel loading ---

    def _load_channels(self):
        portal_id = self.portal_combo.currentData()
        if not portal_id:
            QMessageBox.information(self, "Load", "Please select a portal first.")
            return
        portal = self.config.get_portal(portal_id)
        if not portal:
            return

        self.btn_load.setEnabled(False)
        self.channel_panel.clear()

        self._channel_loader = ChannelLoader(portal)
        self._channel_loader.finished.connect(self._on_channels_loaded)
        self._channel_loader.error.connect(self._on_channel_error)
        self._channel_loader.progress.connect(self.statusBar().showMessage)
        self._channel_loader.start()

    def _on_channels_loaded(self, channels: list, genres: dict):
        self.channel_panel.load_channels(channels, genres)
        self.btn_load.setEnabled(True)
        self.statusBar().showMessage(f"Loaded {len(channels)} channels")

    def _on_channel_error(self, msg: str):
        self.btn_load.setEnabled(True)
        self.statusBar().showMessage(f"Error: {msg}")
        QMessageBox.critical(self, "Connection Error", msg)

    # ------------------------------------------------------- Channel select ---

    def _on_channel_selected(self, channel: dict):
        self._current_channel = channel
        self._tried_macs = set()
        name = channel.get("name", "Unknown")
        self.statusBar().showMessage(f"Loading stream: {name}…")
        self.player.show_status(f"Connecting…\n{name}")

        ch_id = str(channel.get("id", ""))
        self.epg_widget.set_channel(name, ch_id)

        portal_id = self.portal_combo.currentData()
        portal = self.config.get_portal(portal_id)
        if not portal:
            return

        self._start_stream_resolver(portal)

        self._epg_loader = EPGLoader(portal, channel)
        self._epg_loader.finished.connect(self.epg_widget.set_epg_data)
        self._epg_loader.start()

    def _start_stream_resolver(self, portal):
        self._stream_resolver = StreamResolver(
            portal, self._current_channel, skip_macs=self._tried_macs
        )
        self._stream_resolver.trying.connect(self._on_stream_trying)
        self._stream_resolver.resolved.connect(self._on_stream_resolved)
        self._stream_resolver.error.connect(self._on_stream_error)
        self._stream_resolver.start()

    def _on_stream_trying(self, mac: str):
        ch = self._current_channel
        name = ch.get("name", "Unknown") if ch else "Unknown"
        self.player.show_status(f"Connecting…\n{name}\n\nMAC: {mac}")
        self.statusBar().showMessage(f"Trying MAC {mac} for {name}…")

    def _on_stream_resolved(self, url: str, mac: str):
        ch = self._current_channel
        name = ch.get("name", "Unknown") if ch else "Unknown"
        self._tried_macs.add(mac)  # accumulate — never retry a MAC that already played
        self.player.play_url(url, name)
        self.statusBar().showMessage(f"Playing: {name}  [MAC: {mac}]")

    def _on_stream_error(self, msg: str):
        self.statusBar().showMessage(f"Stream error: {msg}")
        self.player.show_status(f"Stream error:\n{msg}", "#f44336")
        QMessageBox.warning(self, "Stream Error", f"Could not load stream:\n{msg}")

    def _on_playback_failed(self):
        """VLC could not play the resolved URL — try the next MAC."""
        ch = self._current_channel
        if not ch:
            return
        portal_id = self.portal_combo.currentData()
        portal = self.config.get_portal(portal_id)
        if not portal or not portal.try_all_macs:
            self.player.show_status("Stream failed.", "#f44336")
            self.statusBar().showMessage("Stream failed.")
            return

        # _tried_macs already contains the MAC that was used for the last
        # stream resolution (set in _on_stream_resolved). No need to add more.
        remaining = [m for m in portal.macs if m not in self._tried_macs]
        if not remaining:
            self.player.show_status("Stream failed.\nNo more MAC addresses to try.", "#f44336")
            self.statusBar().showMessage("Stream failed — no more MACs to try.")
            return

        name = ch.get("name", "Unknown")
        failed_mac = next(iter(self._tried_macs), "")
        self.player.show_status(
            f"Stream failed with MAC {failed_mac}\nTrying next…\n{name}", "#f87c35"
        )
        self.statusBar().showMessage(f"Stream failed, trying next MAC for {name}…")
        self._start_stream_resolver(portal)

    # -------------------------------------------------------------- Fullscreen ---

    def _toggle_fullscreen(self):
        self._is_fullscreen = not self._is_fullscreen
        if self._is_fullscreen:
            self.channel_panel.hide()
            self.epg_widget.hide()
            for tb in self.findChildren(QToolBar):
                tb.hide()
            self.menuBar().hide()
            self.statusBar().hide()
            self.showFullScreen()
        else:
            self.channel_panel.show()
            self.epg_widget.show()
            for tb in self.findChildren(QToolBar):
                tb.show()
            self.menuBar().show()
            self.statusBar().show()
            self.showNormal()
        self.player.set_fullscreen_icon(self._is_fullscreen)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._is_fullscreen:
            self._toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    # ----------------------------------------------------------------- Misc ---

    def _about(self):
        QMessageBox.about(
            self, "About MacPlayer",
            "MacPlayer v1.0\n\n"
            "Desktop IPTV player for Stalker/MAC-based portals.\n\n"
            "Requires VLC media player for video playback.\n"
            "Download: https://www.videolan.org/vlc/",
        )

    def closeEvent(self, event):
        self.config.volume = self.player.get_volume()
        self.config.save()
        self.player.cleanup()
        event.accept()
