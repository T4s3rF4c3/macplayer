from PySide6.QtCore import QThread, Signal
import stb


class ChannelLoader(QThread):
    """Loads channels and genres from a portal in the background."""
    finished = Signal(list, dict)   # channels, genres
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, portal, parent=None):
        super().__init__(parent)
        self.portal = portal

    def run(self):
        p = self.portal
        if not p.macs:
            self.error.emit("No MAC addresses configured for this portal.")
            return

        for mac in p.macs:
            try:
                self.progress.emit(f"Discovering portal URL with {mac}...")
                url = stb.getUrl(p.url, p.proxy or None)
                if not url:
                    self.progress.emit(f"URL discovery failed for {mac}, trying next...")
                    continue

                self.progress.emit(f"Authenticating {mac}...")
                token = stb.getToken(url, mac, p.proxy or None)
                if not token:
                    self.progress.emit(f"Authentication failed for {mac}, trying next...")
                    continue

                stb.getProfile(url, mac, token, p.proxy or None)

                self.progress.emit("Loading channel list...")
                channels = stb.getAllChannels(url, mac, token, p.proxy or None)
                if not channels:
                    self.progress.emit(f"No channels returned for {mac}, trying next...")
                    continue

                self.progress.emit("Loading genres...")
                genres = stb.getGenreNames(url, mac, token, p.proxy or None) or {}

                # Attach connection info to each channel for later stream resolution
                for ch in channels:
                    ch["_portal_url"] = url
                    ch["_mac"] = mac
                    ch["_token"] = token
                    ch["_proxy"] = p.proxy or None

                self.finished.emit(channels, genres)
                return

            except Exception as e:
                self.progress.emit(f"Error with {mac}: {e}")
                continue

        self.error.emit("Failed to connect with any MAC address.")


class StreamResolver(QThread):
    """Resolves the playable stream URL for a channel."""
    resolved = Signal(str, str)   # stream_url, mac_used
    error = Signal(str)
    trying = Signal(str)          # mac currently being attempted

    def __init__(self, portal, channel, skip_macs=None, parent=None):
        super().__init__(parent)
        self.portal = portal
        self.channel = channel
        self.skip_macs: set = set(skip_macs or [])

    def run(self):
        p = self.portal
        ch = self.channel

        url = ch.get("_portal_url")
        mac = ch.get("_mac")
        token = ch.get("_token")
        proxy = ch.get("_proxy")
        cmd = ch.get("cmd", "")

        if not all([url, cmd]):
            self.error.emit("Missing connection info — reload channels and try again.")
            return

        try:
            # Try primary MAC first (unless it's been skipped)
            if mac and mac not in self.skip_macs and token:
                self.trying.emit(mac)
                stream_url = stb.getLink(url, mac, token, cmd, proxy)
                if stream_url:
                    self.resolved.emit(stream_url, mac)
                    return

            # Try remaining MACs
            if p.try_all_macs:
                for alt_mac in p.macs:
                    if alt_mac == mac or alt_mac in self.skip_macs:
                        continue
                    try:
                        self.trying.emit(alt_mac)
                        alt_token = stb.getToken(url, alt_mac, proxy)
                        if not alt_token:
                            continue
                        stream_url = stb.getLink(url, alt_mac, alt_token, cmd, proxy)
                        if stream_url:
                            self.resolved.emit(stream_url, alt_mac)
                            return
                    except Exception:
                        continue

            self.error.emit("Could not resolve stream URL for any MAC address.")
        except Exception as e:
            self.error.emit(str(e))


class EPGLoader(QThread):
    """Loads EPG data for the current portal session."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, portal, channel, parent=None):
        super().__init__(parent)
        self.portal = portal
        self.channel = channel

    def run(self):
        ch = self.channel
        url = ch.get("_portal_url")
        mac = ch.get("_mac")
        token = ch.get("_token")
        proxy = ch.get("_proxy")

        if not all([url, mac, token]):
            return

        try:
            data = stb.getEpg(url, mac, token, 24, proxy)
            if data:
                self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))
