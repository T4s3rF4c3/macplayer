from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QTimer


class EPGWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._epg_data: dict = {}
        self._channel_id: str = ""
        self._setup_ui()

        # Refresh display every minute so progress bar stays accurate
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_display)
        self._refresh_timer.start(60_000)

    # ------------------------------------------------------------------ UI ---

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        header = QLabel("Programme Guide")
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #ccc;")
        layout.addWidget(header)

        self.ch_label = QLabel("—")
        self.ch_label.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.ch_label)

        # NOW block
        now_frame = QFrame()
        now_frame.setStyleSheet("""
            QFrame {
                background: #1b2d3e;
                border: 1px solid #0078d4;
                border-radius: 6px;
            }
        """)
        now_layout = QVBoxLayout(now_frame)
        now_layout.setContentsMargins(10, 10, 10, 10)
        now_layout.setSpacing(4)

        now_badge = QLabel("NOW")
        now_badge.setFixedWidth(36)
        now_badge.setAlignment(Qt.AlignCenter)
        now_badge.setStyleSheet(
            "background: #0078d4; color: white; font-size: 9px; "
            "font-weight: bold; padding: 2px 4px; border-radius: 3px;"
        )

        self.now_title = QLabel("—")
        self.now_title.setStyleSheet("font-weight: bold; color: #eee; font-size: 13px;")
        self.now_title.setWordWrap(True)

        self.now_time = QLabel("")
        self.now_time.setStyleSheet("color: #778; font-size: 11px;")

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar { background: #2e2e2e; border-radius: 2px; border: none; }
            QProgressBar::chunk { background: #0078d4; border-radius: 2px; }
        """)

        self.now_desc = QLabel("")
        self.now_desc.setStyleSheet("color: #888; font-size: 11px;")
        self.now_desc.setWordWrap(True)
        self.now_desc.setMaximumHeight(56)

        for w in (now_badge, self.now_title, self.now_time,
                  self.progress, self.now_desc):
            now_layout.addWidget(w)

        layout.addWidget(now_frame)

        # NEXT block
        next_frame = QFrame()
        next_frame.setStyleSheet("""
            QFrame {
                background: #212121;
                border: 1px solid #333;
                border-radius: 6px;
            }
        """)
        next_layout = QVBoxLayout(next_frame)
        next_layout.setContentsMargins(10, 10, 10, 10)
        next_layout.setSpacing(4)

        next_badge = QLabel("NEXT")
        next_badge.setFixedWidth(36)
        next_badge.setAlignment(Qt.AlignCenter)
        next_badge.setStyleSheet(
            "background: #3a3a3a; color: #aaa; font-size: 9px; "
            "font-weight: bold; padding: 2px 4px; border-radius: 3px;"
        )

        self.next_title = QLabel("—")
        self.next_title.setStyleSheet("color: #ccc; font-size: 12px;")
        self.next_title.setWordWrap(True)

        self.next_time = QLabel("")
        self.next_time.setStyleSheet("color: #666; font-size: 11px;")

        for w in (next_badge, self.next_title, self.next_time):
            next_layout.addWidget(w)

        layout.addWidget(next_frame)

        # Schedule list
        sched_lbl = QLabel("UPCOMING")
        sched_lbl.setStyleSheet(
            "color: #666; font-size: 10px; font-weight: bold; margin-top: 4px;"
        )
        layout.addWidget(sched_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._sched_container = QWidget()
        self._sched_layout = QVBoxLayout(self._sched_container)
        self._sched_layout.setContentsMargins(0, 0, 0, 0)
        self._sched_layout.setSpacing(0)
        self._sched_layout.addStretch()

        scroll.setWidget(self._sched_container)
        layout.addWidget(scroll)

        self.setMinimumWidth(200)
        self.setMaximumWidth(270)

    # --------------------------------------------------------------- Public ---

    def set_channel(self, channel_name: str, channel_id: str):
        self.ch_label.setText(channel_name)
        self._channel_id = channel_id
        self._refresh_display()

    def set_epg_data(self, epg_data: dict):
        self._epg_data = epg_data
        self._refresh_display()

    def clear(self):
        self.ch_label.setText("—")
        self.now_title.setText("—")
        self.now_time.setText("")
        self.now_desc.setText("")
        self.progress.setValue(0)
        self.next_title.setText("—")
        self.next_time.setText("")
        self._clear_schedule()

    # -------------------------------------------------------------- Private ---

    def _refresh_display(self):
        if not self._channel_id or not self._epg_data:
            return

        programmes = self._epg_data.get(str(self._channel_id), [])
        if not programmes:
            return

        now = datetime.now()
        now_prog = next_prog = None
        upcoming = []

        for prog in programmes:
            try:
                start = datetime.fromtimestamp(int(prog.get("start_timestamp", 0)))
                stop = datetime.fromtimestamp(int(prog.get("stop_timestamp", 0)))
            except Exception:
                continue

            if start <= now < stop:
                now_prog = (prog, start, stop)
            elif start > now:
                if next_prog is None:
                    next_prog = (prog, start, stop)
                elif len(upcoming) < 8:
                    upcoming.append((prog, start, stop))

        if now_prog:
            prog, start, stop = now_prog
            self.now_title.setText(prog.get("name", "Unknown"))
            self.now_time.setText(
                f"{start.strftime('%H:%M')} – {stop.strftime('%H:%M')}"
            )
            self.now_desc.setText(prog.get("descr", ""))
            total = (stop - start).total_seconds()
            elapsed = (now - start).total_seconds()
            self.progress.setValue(int(elapsed / total * 100) if total else 0)

        if next_prog:
            prog, start, stop = next_prog
            self.next_title.setText(prog.get("name", "Unknown"))
            self.next_time.setText(
                f"{start.strftime('%H:%M')} – {stop.strftime('%H:%M')}"
            )

        self._clear_schedule()
        for prog, start, stop in upcoming:
            row = QLabel(
                f"  {start.strftime('%H:%M')}  {prog.get('name', '?')}"
            )
            row.setStyleSheet(
                "color: #999; font-size: 11px; padding: 4px 0; "
                "border-bottom: 1px solid #1e1e1e;"
            )
            self._sched_layout.insertWidget(
                self._sched_layout.count() - 1, row
            )

    def _clear_schedule(self):
        while self._sched_layout.count() > 1:
            item = self._sched_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
