from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QComboBox, QListWidget, QListWidgetItem, QLabel,
)
from PySide6.QtCore import Qt, Signal


_LIST_STYLE = """
    QListWidget {
        background: #1a1a1a;
        border: 1px solid #2e2e2e;
        border-radius: 4px;
        color: #ddd;
        font-size: 13px;
        outline: none;
    }
    QListWidget::item {
        padding: 8px 10px;
        border-bottom: 1px solid #222;
        min-height: 20px;
    }
    QListWidget::item:selected {
        background: #0078d4;
        color: white;
        border-bottom-color: #0060aa;
    }
    QListWidget::item:hover:!selected {
        background: #242424;
    }
"""

_SEARCH_STYLE = """
    QLineEdit {
        background: #252525;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        padding: 5px 10px;
        color: #ddd;
        font-size: 13px;
    }
    QLineEdit:focus { border-color: #0078d4; }
"""

_COMBO_STYLE = """
    QComboBox {
        background: #252525;
        color: #ddd;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 12px;
    }
    QComboBox::drop-down { border: none; width: 20px; }
    QComboBox QAbstractItemView {
        background: #252525;
        color: #ddd;
        selection-background-color: #0078d4;
        border: 1px solid #3a3a3a;
    }
"""


class _ChannelItem(QListWidgetItem):
    def __init__(self, ch: dict):
        number = ch.get("number", "") or ch.get("tv_genre_id", "")
        name = ch.get("name", "Unknown")
        label = f"{number}. {name}" if number else name
        super().__init__(label)
        self.channel_data = ch


class ChannelPanel(QWidget):
    channel_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_channels: list = []
        self._genres: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Genre combo
        genre_row = QHBoxLayout()
        genre_row.setSpacing(4)
        genre_lbl = QLabel("Genre")
        genre_lbl.setStyleSheet("color: #888; font-size: 11px;")
        self.genre_combo = QComboBox()
        self.genre_combo.setStyleSheet(_COMBO_STYLE)
        self.genre_combo.addItem("All Genres", "all")
        self.genre_combo.currentIndexChanged.connect(self._apply_filter)
        genre_row.addWidget(genre_lbl)
        genre_row.addWidget(self.genre_combo, 1)
        layout.addLayout(genre_row)

        # Search
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search channels…")
        self.search_box.setStyleSheet(_SEARCH_STYLE)
        self.search_box.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_box)

        # Count label
        self.count_label = QLabel("No channels loaded")
        self.count_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.count_label)

        # Channel list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(_LIST_STYLE)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        self.setMinimumWidth(210)
        self.setMaximumWidth(320)

    # --------------------------------------------------------------- Public ---

    def load_channels(self, channels: list, genres: dict):
        self._all_channels = channels
        self._genres = genres

        # Rebuild genre combo preserving current selection
        saved = self.genre_combo.currentData()
        self.genre_combo.blockSignals(True)
        self.genre_combo.clear()
        self.genre_combo.addItem("All Genres", "all")

        seen = set()
        for ch in channels:
            gid = str(ch.get("tv_genre_id", ch.get("genre_id", "")) or "")
            if gid and gid not in seen:
                seen.add(gid)
                self.genre_combo.addItem(genres.get(gid, f"Genre {gid}"), gid)

        idx = self.genre_combo.findData(saved)
        self.genre_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.genre_combo.blockSignals(False)

        self._apply_filter()

    def clear(self):
        self._all_channels = []
        self._genres = {}
        self.list_widget.clear()
        self.genre_combo.clear()
        self.genre_combo.addItem("All Genres", "all")
        self.count_label.setText("No channels loaded")
        self.search_box.clear()

    # -------------------------------------------------------------- Private ---

    def _apply_filter(self):
        search = self.search_box.text().strip().lower()
        genre = self.genre_combo.currentData()

        self.list_widget.clear()
        visible = 0

        for ch in self._all_channels:
            if genre and genre != "all":
                ch_genre = str(ch.get("tv_genre_id", ch.get("genre_id", "")) or "")
                if ch_genre != genre:
                    continue
            if search and search not in ch.get("name", "").lower():
                continue

            self.list_widget.addItem(_ChannelItem(ch))
            visible += 1

        total = len(self._all_channels)
        self.count_label.setText(
            f"{visible} of {total} channels" if total else "No channels loaded"
        )

    def _on_item_clicked(self, item: _ChannelItem):
        self.channel_selected.emit(item.channel_data)
