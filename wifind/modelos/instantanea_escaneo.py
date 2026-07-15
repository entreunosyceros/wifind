"""Instantánea de un escaneo WiFi."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from wifind.wifi.red import RedWifi


@dataclass
class InstantaneaEscaneo:
    timestamp: float
    networks: list[RedWifi] = field(default_factory=list)

    @property
    def numero_redes(self) -> int:
        return len(self.networks)

    @property
    def senal_media_dbm(self) -> float | None:
        if not self.networks:
            return None
        return sum(n.signal_dbm for n in self.networks) / len(self.networks)

    def a_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "networks": [n.a_dict() for n in self.networks],
        }

    @classmethod
    def desde_dict(cls, data: dict) -> InstantaneaEscaneo:
        return cls(
            timestamp=float(data.get("timestamp", time.time())),
            networks=[RedWifi.desde_dict(n) for n in data.get("networks", [])],
        )

    @classmethod
    def desde_redes(cls, networks: list[RedWifi]) -> InstantaneaEscaneo:
        return cls(timestamp=time.time(), networks=list(networks))
