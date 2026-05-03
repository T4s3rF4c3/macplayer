# MacPlayer

A desktop IPTV player for Stalker/MAC-based portals, built with PySide6 and VLC.

## Download

Pre-built binaries are available on the [Releases](../../releases/latest) page:

| Platform | File |
|---|---|
| Windows | `MacPlayer-windows.zip` — extract and run `MacPlayer.exe` |
| macOS | `MacPlayer.dmg` — open and drag to Applications |

> **macOS note:** The app is unsigned. On first launch right-click → Open to bypass Gatekeeper.
>
> **Both platforms require [VLC](https://www.videolan.org/vlc/) to be installed.**

## Features

- Connect to multiple Stalker Portal-based IPTV services
- Multi-MAC support with automatic failover during playback
- Import portals from TXT files (extracts URLs and MAC addresses automatically)
- Test all MAC addresses at once and remove invalid ones
- Live channel list with genre filtering
- EPG (Electronic Programme Guide) panel
- Proxy support per portal
- EPG timezone offset per portal
- Fullscreen mode (button or Escape key)
- Dark UI with VLC-powered video playback
- Stream status overlay (shows which MAC is being tried)
- Config persisted to `~/.macplayer/config.json`

## Requirements

- Python 3.10+
- [VLC media player](https://www.videolan.org/vlc/) installed on the system
- Dependencies listed in `requirements.txt`

## Installation

```bash
git clone https://github.com/T4s3rF4c3/macplayer.git
cd macplayer

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

**First steps:**

1. Click **+ Add Portal** in the toolbar (or **Portals → Add Portal…**)
2. Enter a name, portal URL, and one or more MAC addresses — or use **Import TXT** to extract them from a file
3. Click **Load Channels** — the channel list populates on the left
4. Click a channel to start playback

## Portal Configuration

| Field | Description |
|---|---|
| Name | Friendly label shown in the portal selector |
| URL | Portal base URL (e.g. `http://your-portal.com:8080`) |
| MAC addresses | One per line; used in order as fallback |
| Import TXT | Extracts URLs (`/c/` pattern) and MACs from one or more `.txt` files |
| Test Connection | Checks every MAC, shows expiry date, offers to remove invalid ones |
| Proxy | Optional HTTP proxy (`http://host:port`) |
| EPG offset | Hours to shift EPG timestamps (e.g. `+1` for CET) |
| Try all MACs | Automatically try the next MAC if a stream fails or drops |

## MAC Failover

When **Try all MACs** is enabled MacPlayer will:

1. Show a status overlay in the player indicating which MAC is being tried
2. Detect stream failures via VLC events (error, end, stall) within seconds
3. Automatically retry with the next MAC in the list
4. Display a message when all MACs have been exhausted

## Building

Pushing a `v*.*.*` tag triggers GitHub Actions to build both platforms and publish a release automatically.

For local builds, install build dependencies first:

```bash
pip install -r requirements-dev.txt
```

**macOS** — produces `dist/MacPlayer.app` and optionally a `.dmg`:

```bash
./build.sh
# Optional DMG: brew install create-dmg
```

**Windows** — produces `dist\MacPlayer\MacPlayer.exe` and a `.zip`:

```bat
build.bat
```

> VLC must be installed on the target machine: https://www.videolan.org/vlc/

## Project Structure

```
macplayer/
├── main.py              # Entry point; QApplication and dark palette
├── config.py            # Portal and Config data classes; JSON persistence
├── stb.py               # Stalker Portal API (URL discovery, auth, channels, EPG, links)
├── worker.py            # QThread workers: ChannelLoader, StreamResolver, EPGLoader
├── requirements.txt     # Runtime dependencies
├── requirements-dev.txt # Build dependencies (pyinstaller, Pillow)
├── MacPlayer.spec       # PyInstaller build spec (macOS + Windows)
├── build.sh             # macOS build script
├── build.bat            # Windows build script
├── create_icon.py       # Generates .icns and .ico from code
├── assets/              # App icons (generated, not committed)
└── ui/
    ├── main_window.py       # Main window; portal CRUD, channel loading, stream orchestration
    ├── channel_panel.py     # Channel list with genre filter
    ├── player_widget.py     # VLC player with stream failure detection
    ├── epg_widget.py        # EPG sidebar
    └── portal_dialog.py     # Add/edit portal dialog (incl. TXT import + MAC testing)
```

## Dependencies

| Package | Purpose |
|---|---|
| `PySide6` | Qt UI framework |
| `python-vlc` | VLC bindings for video playback |
| `requests` | HTTP client for Stalker Portal API calls |
