from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ConfigTUI:
    status_fmt: str = ""
    last_update_fmt: str = ""
    update_interval: Optional[int] = None
    macro1: str = ""
    macro2: str = ""
    macro3: str = ""
    macro4: str = ""

    def parse_kwargs(self, kw: Dict) -> None:
        if status_fmt := kw.get("status_fmt"):
            self.status_fmt = status_fmt
        if last_update_fmt := kw.get("last_update_fmt"):
            self.last_update_fmt = last_update_fmt
        if update_interval := kw.get("update_interval"):
            self.update_interval = update_interval
        if macro1 := kw.get("macro1"):
            self.macro1 = macro1
        if macro2 := kw.get("macro2"):
            self.macro2 = macro2
        if macro3 := kw.get("macro3"):
            self.macro3 = macro3
        if macro4 := kw.get("macro4"):
            self.macro4 = macro4
