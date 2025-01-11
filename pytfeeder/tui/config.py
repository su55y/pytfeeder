from dataclasses import dataclass
from typing import Dict


@dataclass
class ConfigTUI:
    status_fmt: str = ""
    last_update_fmt: str = ""

    def parse_kwargs(self, kw: Dict) -> None:
        if status_fmt := kw.get("status_fmt"):
            self.status_fmt = status_fmt
        if last_update_fmt := kw.get("last_update_fmt"):
            self.last_update_fmt = last_update_fmt
