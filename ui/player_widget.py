import sys
import time

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QTimer, Signal

VLC_AVAILABLE = False
try:
    import vlc
    VLC_AVAILABLE = True
except Exception:
    pass

_OPEN_TIMEOUT    = 12
_BUFFER_TIMEOUT  = 20
_FREEZE_TIMEOUT  = 15
_AUTOHIDE_MS     = 3000

_BTN = """
    QPushButton {{
        background: {bg};
        color: white;
        border: none;
        border-radius: 4px;
        font-size: {fs}px;
        padding: 0;
    }}
    QPushButton:hover {{ background: #555; }}
    QPushButton:pressed {{ background: #0078d4; }}
"""

_SLIDER = """
    QSlider::groove:horizontal {
        height: 4px; background: #444; border-radius: 2px;
    }
    QSlider::handle:horizontal {
        background: #0078d4; width: 14px; height: 14px;
        margin: -5px 0; border-radius: 7px;
    }
    QSlider::sub-page:horizontal {
        background: #0078d4; border-radius: 2px;
    }
"""


class VideoFrame(QFrame):
    mouse_moved    = Signal()
    double_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: black;")
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        self.mouse_moved.emit()
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class PlayerWidget(QWidget):
    playback_failed      = Signal()
    fullscreen_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        self._vlc_instance  = None
        self._media_player  = None
        self._volume        = 80
        self._channel_name  = ""

        self._active: bool                  = False
        self._was_playing: bool             = False
        self._start_time: float             = 0.0
        self._play_start: float             = 0.0
        self._buffering_since: float | None = None
        self._last_vlc_time: int            = -1
        self._frozen_secs: int              = 0
        self._vlc_error_flag: bool          = False
        self._last_read_bytes: int          = 0

        self._autohide: bool        = False
        self._controls_hidden: bool = False

        self._setup_ui()
        self._setup_vlc()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._monitor)
        self._poll_timer.start(1000)

        self._autohide_timer = QTimer(self)
        self._autohide_timer.setSingleShot(True)
        self._autohide_timer.timeout.connect(self._hide_controls)

    # ------------------------------------------------------------------ UI ---

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_frame = VideoFrame(self)
        self.video_frame.mouse_moved.connect(self._on_mouse_moved)
        self.video_frame.double_clicked.connect(self.fullscreen_requested)

        self.placeholder = QLabel(
            "Select a channel to start playback\n\n"
            + ("" if VLC_AVAILABLE else
               "VLC not found — install python-vlc and VLC media player"),
            self.video_frame,
        )
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet(
            "color: #666; font-size: 14px; background: transparent;"
        )
        layout.addWidget(self.video_frame)

        # Control bar
        self._bar = QWidget()
        self._bar.setFixedHeight(52)
        self._bar.setStyleSheet("background: #1a1a1a; border-top: 1px solid #2e2e2e;")
        bar_layout = QHBoxLayout(self._bar)
        bar_layout.setContentsMargins(10, 6, 10, 6)
        bar_layout.setSpacing(8)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(36, 36)
        self.btn_play.setStyleSheet(_BTN.format(bg="#333", fs=17))
        self.btn_play.clicked.connect(self.toggle_play)

        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setFixedSize(36, 36)
        self.btn_stop.setStyleSheet(_BTN.format(bg="#333", fs=17))
        self.btn_stop.clicked.connect(self.stop)

        self.ch_label = QLabel("")
        self.ch_label.setStyleSheet("color: #bbb; font-size: 13px;")

        # Stats inline in the bar: elapsed time · bitrate · buffer state
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(
            "color: #666; font-size: 12px;"
            "font-family: 'Consolas', 'Courier New', monospace;"
        )

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        sep.setStyleSheet("background: #333; border: none;")

        self.vol_icon = QLabel("🔊")
        self.vol_icon.setStyleSheet("font-size: 16px;")

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self._volume)
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.setStyleSheet(_SLIDER)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        self.btn_fs = QPushButton("⛶")
        self.btn_fs.setFixedSize(36, 36)
        self.btn_fs.setStyleSheet(_BTN.format(bg="#333", fs=17))
        self.btn_fs.setToolTip("Toggle fullscreen  (double-click video)")
        self.btn_fs.clicked.connect(self.fullscreen_requested)

        for w in (self.btn_play, self.btn_stop, self.ch_label, self.stats_label,
                  spacer, sep, self.vol_icon, self.volume_slider, self.btn_fs):
            bar_layout.addWidget(w)

        layout.addWidget(self._bar)

    # ----------------------------------------------------------------- VLC ---

    def _setup_vlc(self):
        if not VLC_AVAILABLE:
            return
        try:
            self._vlc_instance = vlc.Instance("--no-xlib --quiet")
            self._media_player = self._vlc_instance.media_player_new()
            self._attach_output()
            self._media_player.audio_set_volume(self._volume)
            self._register_vlc_events()
        except Exception as e:
            print(f"VLC init error: {e}")
            self._vlc_instance = None
            self._media_player = None

    def _attach_output(self):
        wid = int(self.video_frame.winId())
        if sys.platform == "win32":
            self._media_player.set_hwnd(wid)
        elif sys.platform == "darwin":
            self._media_player.set_nsobject(wid)
        else:
            self._media_player.set_xwindow(wid)

    def _register_vlc_events(self):
        em = self._media_player.event_manager()
        for event_type in (
            vlc.EventType.MediaPlayerEncounteredError,
            vlc.EventType.MediaPlayerEndReached,
            vlc.EventType.MediaPlayerStopped,
        ):
            em.event_attach(event_type, self._on_vlc_event)

    def _on_vlc_event(self, event):
        if self._active:
            self._vlc_error_flag = True

    # -------------------------------------------------------------- Auto-hide ---

    def set_autohide(self, enabled: bool):
        self._autohide = enabled
        if enabled:
            self._autohide_timer.start(_AUTOHIDE_MS)
        else:
            self._autohide_timer.stop()
            self._show_controls()

    def _on_mouse_moved(self):
        if self._autohide:
            self._show_controls()
            self._autohide_timer.start(_AUTOHIDE_MS)

    def _hide_controls(self):
        self._controls_hidden = True
        self._bar.hide()
        self.setCursor(Qt.BlankCursor)

    def _show_controls(self):
        self._controls_hidden = False
        self._bar.show()
        self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        self._on_mouse_moved()
        super().mouseMoveEvent(event)

    # ----------------------------------------------------------------- Stats ---

    def _update_stats(self):
        if not self._was_playing or not self._active:
            self.stats_label.setText("")
            return

        parts = []

        elapsed = int(time.monotonic() - self._play_start) if self._play_start > 0 else 0
        h, rem  = divmod(elapsed, 3600)
        m, s    = divmod(rem, 60)
        parts.append(f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}")

        # Bitrate via read_bytes delta — avoids VLC's unreliable input_bitrate float
        if self._media_player and VLC_AVAILABLE:
            try:
                media = self._media_player.get_media()
                if media:
                    st = vlc.MediaStats()
                    if media.get_stats(st) and st.read_bytes > 0:
                        delta = st.read_bytes - self._last_read_bytes
                        if self._last_read_bytes > 0 and delta > 0:
                            kbps = delta * 8 / 1000
                            parts.append(
                                f"{kbps / 1000:.1f} Mbps" if kbps >= 1000 else f"{kbps:.0f} kbps"
                            )
                        self._last_read_bytes = st.read_bytes
            except Exception:
                pass

        if self._buffering_since is not None:
            parts.append("Buffering…")

        self.stats_label.setText("  ·  ".join(parts))

    # --------------------------------------------------------------- Public ---

    def show_status(self, text: str, color: str = "#888"):
        self.placeholder.setText(text)
        self.placeholder.setStyleSheet(
            f"color: {color}; font-size: 14px; background: transparent;"
        )
        self.placeholder.show()

    def play_url(self, url: str, channel_name: str = ""):
        self._active          = True
        self._was_playing     = False
        self._start_time      = time.monotonic()
        self._play_start      = 0.0
        self._buffering_since = None
        self._last_vlc_time   = -1
        self._frozen_secs     = 0
        self._vlc_error_flag  = False
        self._last_read_bytes = 0

        self._channel_name = channel_name
        self.ch_label.setText(channel_name)
        self.stats_label.setText("")
        self.show_status(f"Loading stream…\n{channel_name}", "#888")

        if self._media_player is None:
            self.show_status(f"VLC not available.\n\nStream URL:\n{url}", "#f44336")
            self._active = False
            return

        self._attach_output()
        media = self._vlc_instance.media_new(url)
        self._media_player.set_media(media)
        self._media_player.play()
        self.btn_play.setText("⏸")

    def toggle_play(self):
        if self._media_player is None:
            return
        if self._media_player.is_playing():
            self._media_player.pause()
        else:
            self._media_player.play()

    def stop(self):
        self._active         = False
        self._vlc_error_flag = False
        if self._media_player:
            self._media_player.stop()
        self.btn_play.setText("▶")
        self.ch_label.setText("")
        self.stats_label.setText("")
        self._channel_name = ""
        self.show_status("Select a channel to start playback")

    def set_volume(self, value: int):
        self.volume_slider.setValue(value)

    def get_volume(self) -> int:
        return self._volume

    def set_fullscreen_icon(self, is_fullscreen: bool):
        self.btn_fs.setText("✕" if is_fullscreen else "⛶")

    def cleanup(self):
        self._active = False
        if self._media_player:
            self._media_player.stop()
        if self._vlc_instance:
            self._vlc_instance.release()

    # -------------------------------------------------------------- Private ---

    def _fail(self):
        self._active = False
        self.playback_failed.emit()

    def _monitor(self):
        if not self._media_player:
            return

        if self._vlc_error_flag:
            self._vlc_error_flag = False
            if self._active:
                self._fail()
            return

        is_playing = self._media_player.is_playing()
        self.btn_play.setText("⏸" if is_playing else "▶")

        if is_playing:
            if self.placeholder.isVisible():
                self.placeholder.hide()
            if not self._was_playing:
                self._play_start = time.monotonic()
            self._was_playing     = True
            self._buffering_since = None

            vlc_time = self._media_player.get_time()
            if vlc_time > 0:
                if vlc_time == self._last_vlc_time:
                    self._frozen_secs += 1
                    if self._frozen_secs >= _FREEZE_TIMEOUT:
                        self._update_stats()
                        self._fail()
                        return
                else:
                    self._last_vlc_time = vlc_time
                    self._frozen_secs   = 0

            self._update_stats()
            return

        self._update_stats()

        if not self._active:
            return

        now   = time.monotonic()
        state = self._media_player.get_state()

        if state == vlc.State.Error:
            self._fail()

        elif state in (vlc.State.Ended, vlc.State.Stopped):
            self._fail()

        elif state == vlc.State.Buffering:
            if self._buffering_since is None:
                self._buffering_since = now
            elif now - self._buffering_since >= _BUFFER_TIMEOUT:
                self._fail()

        elif state in (vlc.State.Opening, vlc.State.NothingSpecial):
            if now - self._start_time >= _OPEN_TIMEOUT:
                self._fail()

    def _on_volume_changed(self, value: int):
        self._volume = value
        if self._media_player:
            self._media_player.audio_set_volume(value)
        self.vol_icon.setText("🔇" if value == 0 else "🔉" if value < 50 else "🔊")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.placeholder.setGeometry(self.video_frame.rect())
