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

# How long to wait for VLC to open a stream before giving up (seconds)
_OPEN_TIMEOUT   = 12
# How long a buffering stall may last before we treat it as failure (seconds)
_BUFFER_TIMEOUT = 20
# How long playback time must be frozen before we treat it as a dead stream (seconds)
_FREEZE_TIMEOUT = 15

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
    """Black container that hosts VLC video output."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: black;")
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


class PlayerWidget(QWidget):
    playback_failed = Signal()
    fullscreen_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._vlc_instance  = None
        self._media_player  = None
        self._volume        = 80
        self._channel_name  = ""

        # --- monitoring state (reset on every play_url call) ---
        self._active: bool          = False
        self._was_playing: bool     = False
        self._start_time: float     = 0.0
        self._buffering_since: float | None = None
        self._last_vlc_time: int    = -1   # ms reported by VLC
        self._frozen_secs: int      = 0    # consecutive seconds without time advance
        # Flag set from VLC callback thread; consumed by _monitor on Qt thread
        self._vlc_error_flag: bool  = False

        self._setup_ui()
        self._setup_vlc()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._monitor)
        self._poll_timer.start(1000)

    # ------------------------------------------------------------------ UI ---

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.video_frame = VideoFrame(self)

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

        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet("background: #1a1a1a; border-top: 1px solid #2e2e2e;")
        bar_layout = QHBoxLayout(bar)
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

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

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
        self.btn_fs.setToolTip("Toggle fullscreen")
        self.btn_fs.clicked.connect(self.fullscreen_requested)

        for w in (self.btn_play, self.btn_stop, self.ch_label,
                  spacer, self.vol_icon, self.volume_slider, self.btn_fs):
            bar_layout.addWidget(w)

        layout.addWidget(bar)

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
        """Subscribe to VLC error/end events. Callbacks run on VLC's internal thread."""
        em = self._media_player.event_manager()
        for event_type in (
            vlc.EventType.MediaPlayerEncounteredError,
            vlc.EventType.MediaPlayerEndReached,
            vlc.EventType.MediaPlayerStopped,
        ):
            em.event_attach(event_type, self._on_vlc_event)

    def _on_vlc_event(self, event):
        """Called from VLC thread — only set a flag; Qt UI touched in _monitor."""
        if self._active:
            self._vlc_error_flag = True

    # --------------------------------------------------------------- Public ---

    def show_status(self, text: str, color: str = "#888"):
        self.placeholder.setText(text)
        self.placeholder.setStyleSheet(
            f"color: {color}; font-size: 14px; background: transparent;"
        )
        self.placeholder.show()

    def play_url(self, url: str, channel_name: str = ""):
        # Reset all monitoring state before starting a new stream
        self._active          = True
        self._was_playing     = False
        self._start_time      = time.monotonic()
        self._buffering_since = None
        self._last_vlc_time   = -1
        self._frozen_secs     = 0
        self._vlc_error_flag  = False

        self._channel_name = channel_name
        self.ch_label.setText(channel_name)
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
        self._active = False          # must be set BEFORE calling vlc stop()
        self._vlc_error_flag = False  # discard any pending event
        if self._media_player:
            self._media_player.stop()
        self.btn_play.setText("▶")
        self.ch_label.setText("")
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
        """Mark stream failed and signal main window to try next MAC."""
        self._active = False
        self.playback_failed.emit()

    def _monitor(self):
        """Runs every second on the Qt thread — detects stream failures."""
        if not self._media_player:
            return

        # --- VLC event flag (set from VLC internal thread) ---
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
            self._was_playing     = True
            self._buffering_since = None

            # Detect frozen stream: check that VLC's playback clock advances
            vlc_time = self._media_player.get_time()
            if vlc_time > 0:
                if vlc_time == self._last_vlc_time:
                    self._frozen_secs += 1
                    if self._frozen_secs >= _FREEZE_TIMEOUT:
                        self._fail()
                else:
                    self._last_vlc_time = vlc_time
                    self._frozen_secs   = 0
            return

        if not self._active:
            return

        # --- State-based timeout checks ---
        now   = time.monotonic()
        state = self._media_player.get_state()

        if state == vlc.State.Error:
            self._fail()

        elif state in (vlc.State.Ended, vlc.State.Stopped):
            # Unexpected stop/end — fail regardless of whether we were playing
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
