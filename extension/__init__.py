import Falkon
from PySide6 import QtCore
import urllib.request
import json
import re
import os


class UBlockOrigin(Falkon.PluginInterface, QtCore.QObject):
    def __init__(self):
        super().__init__()
        self._filter_lists = []
        self._compiled_filters = []
        self._cosmetic_filters = []
        self._blocked_count = 0
        self._enabled = True
        self._settings_path = ""
        self._settings_file = ""

        self.EASYLIST_URL = "https://easylist-downloads.adblockplus.org/easylist.txt"
        self.EASYPRIVACY_URL = "https://easylist-downloads.adblockplus.org/easyprivacy.txt"

    def init(self, state, settings_path):
        self._settings_path = settings_path
        self._settings_file = os.path.join(settings_path, "ublock-origin.json")
        self._load_settings()
        self._download_filter_list("EasyList", self.EASYLIST_URL)
        self._download_filter_list("EasyPrivacy", self.EASYPRIVACY_URL)
        print("uBlock Origin for Falkon initialized")

    def unload(self):
        self._save_settings()
        print("uBlock Origin unloaded")

    def test_plugin(self):
        return True

    def _load_settings(self):
        try:
            with open(self._settings_file, "r") as f:
                data = json.load(f)
                self._enabled = data.get("enabled", True)
                self._blocked_count = data.get("blocked_count", 0)
                raw_lists = data.get("filter_lists", [])
                for entry in raw_lists:
                    flt = {
                        "name": entry["name"],
                        "url": entry["url"],
                        "raw": entry.get("raw", ""),
                        "last_updated": entry.get("last_updated", ""),
                        "filter_count": entry.get("filter_count", 0),
                    }
                    if flt["raw"]:
                        parsed = self._parse_filters(flt["raw"])
                        flt["parsed"] = parsed
                        flt["compiled"] = self._compile_network_filters(parsed["network"])
                    else:
                        flt["parsed"] = {"network": [], "cosmetic": []}
                        flt["compiled"] = []
                    self._filter_lists.append(flt)
                self._rebuild_compiled_filters()
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def _save_settings(self):
        try:
            saveable = []
            for flt in self._filter_lists:
                saveable.append({
                    "name": flt["name"],
                    "url": flt["url"],
                    "raw": flt.get("raw", ""),
                    "last_updated": flt.get("last_updated", ""),
                    "filter_count": flt.get("filter_count", 0),
                })
            with open(self._settings_file, "w") as f:
                json.dump({
                    "enabled": self._enabled,
                    "blocked_count": self._blocked_count,
                    "filter_lists": saveable,
                }, f, indent=2)
        except Exception as e:
            print(f"uBO: failed to save settings: {e}")

    def _parse_filters(self, raw_text):
        network = []
        cosmetic = []
        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("!") or line.startswith("["):
                continue
            if "##" in line or "#@#" in line:
                cosmetic.append(line)
            else:
                network.append(line)
        return {"network": network, "cosmetic": cosmetic}

    def _filter_to_regex(self, abp_filter):
        if "||" in abp_filter:
            idx = abp_filter.index("||")
            pattern = abp_filter[idx + 2:]
            pattern = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", "\\?")
            pattern = r"^https?://([^/]+\.)?" + pattern
        elif abp_filter.startswith("|"):
            pattern = "^" + re.escape(abp_filter[1:].rstrip("|")) + "$"
            pattern = pattern.replace(r"\*", ".*")
        elif abp_filter.startswith("/") and abp_filter.endswith("/"):
            pattern = abp_filter[1:-1]
        else:
            pattern = re.escape(abp_filter).replace(r"\*", ".*").replace(r"\?", "\\?")
        try:
            return re.compile(pattern, re.IGNORECASE)
        except re.error:
            return None

    def _compile_network_filters(self, raw_filters):
        compiled = []
        for f in raw_filters:
            rx = self._filter_to_regex(f)
            if rx:
                compiled.append({"raw": f, "regex": rx})
        return compiled

    def _rebuild_compiled_filters(self):
        all_filters = []
        all_cosmetic = []
        for flt in self._filter_lists:
            if "compiled" in flt:
                all_filters.extend(flt["compiled"])
            if "parsed" in flt:
                all_cosmetic.extend(flt["parsed"]["cosmetic"])
        self._compiled_filters = all_filters
        self._cosmetic_filters = all_cosmetic

    def _download_filter_list(self, name, url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
        except Exception as e:
            print(f"uBO: failed to download {name}: {e}")
            return

        parsed = self._parse_filters(data)
        compiled = self._compile_network_filters(parsed["network"])

        entry = {
            "name": name,
            "url": url,
            "raw": data,
            "parsed": parsed,
            "compiled": compiled,
            "last_updated": QtCore.QDateTime.currentDateTime().toString(QtCore.Qt.ISODate),
            "filter_count": len(parsed["network"]) + len(parsed["cosmetic"]),
        }

        replaced = False
        for i, flt in enumerate(self._filter_lists):
            if flt["name"] == name:
                self._filter_lists[i] = entry
                replaced = True
                break
        if not replaced:
            self._filter_lists.append(entry)

        self._rebuild_compiled_filters()
        self._save_settings()
        self._inject_cosmetic_filters()
        print(f"uBO: loaded {name} ({entry['filter_count']} filters)")

    def _inject_cosmetic_filters(self):
        scripts = Falkon.UserScripts()
        existing = scripts.findScript("ubo-cosmetic")
        if existing:
            scripts.remove(existing)

        if not self._cosmetic_filters:
            return

        lines = []
        for cf in self._cosmetic_filters:
            idx = cf.find("##")
            if idx == -1:
                continue
            domain = cf[:idx]
            selector = cf[idx + 2:]
            if selector.startswith(":style"):
                continue
            escaped_sel = selector.replace("'", "\\'").replace('"', '\\"')
            lines.append(
                f"(function(){{"
                f"if(location.hostname==='{domain}'||location.hostname.endsWith('.{domain}')){{"
                f"try{{document.querySelectorAll('{escaped_sel}').forEach(e=>e.style.display='none')}}catch(e){{}}"
                f"}}}})()"
            )

        if not lines:
            return

        script = Falkon.UserScript()
        script.name = "ubo-cosmetic"
        script.runsOnSubFrames = True
        script.worldId = Falkon.UserScript.ApplicationWorld
        script.injectionPoint = Falkon.UserScript.DocumentReady
        script.sourceCode = "\n".join(lines)

    def acceptNavigationRequest(self, tab, url, navigation_type, is_main_frame):
        if not self._enabled or is_main_frame:
            return True

        for f in self._compiled_filters:
            try:
                if f["regex"].search(url):
                    self._blocked_count += 1
                    self._save_settings()
                    return False
            except Exception:
                continue

        return True

    def populateWebViewMenu(self, menu, hit_test_result):
        action = menu.addAction({
            "text": "Block element with uBO",
            "icon": "edit-block-list",
        })
        action.triggered.connect(self._on_block_element)

    def _on_block_element(self):
        print("uBO: block element requested")


Falkon.registerPlugin(UBlockOrigin())
