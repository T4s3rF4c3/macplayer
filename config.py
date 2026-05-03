import json
import os
import uuid
from typing import List, Optional

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".macplayer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


class Portal:
    def __init__(self, id=None, name="", url="", macs=None, proxy="",
                 epg_offset=0, try_all_macs=True):
        self.id = id or str(uuid.uuid4())[:8]
        self.name = name
        self.url = url
        self.macs = macs or []
        self.proxy = proxy
        self.epg_offset = epg_offset
        self.try_all_macs = try_all_macs

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "macs": self.macs,
            "proxy": self.proxy,
            "epg_offset": self.epg_offset,
            "try_all_macs": self.try_all_macs,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id"),
            name=d.get("name", ""),
            url=d.get("url", ""),
            macs=d.get("macs", []),
            proxy=d.get("proxy", ""),
            epg_offset=d.get("epg_offset", 0),
            try_all_macs=d.get("try_all_macs", True),
        )


class Config:
    def __init__(self):
        self.portals: List[Portal] = []
        self.volume: int = 80
        self.last_portal_id: str = ""
        self.load()

    def load(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.portals = [Portal.from_dict(p) for p in data.get("portals", [])]
            self.volume = data.get("volume", 80)
            self.last_portal_id = data.get("last_portal_id", "")
        except Exception as e:
            print(f"Config load error: {e}")

    def save(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = {
            "portals": [p.to_dict() for p in self.portals],
            "volume": self.volume,
            "last_portal_id": self.last_portal_id,
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Config save error: {e}")

    def get_portal(self, portal_id: str) -> Optional[Portal]:
        return next((p for p in self.portals if p.id == portal_id), None)

    def add_portal(self, portal: Portal):
        self.portals.append(portal)
        self.save()

    def update_portal(self, portal: Portal):
        for i, p in enumerate(self.portals):
            if p.id == portal.id:
                self.portals[i] = portal
                self.save()
                return

    def remove_portal(self, portal_id: str):
        self.portals = [p for p in self.portals if p.id != portal_id]
        self.save()
