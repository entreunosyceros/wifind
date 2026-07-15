"""Medición de señal y obstáculos (paredes) en el mapa."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

# Material → (etiqueta UI, atenuación típica en dB a 2,4 GHz)
MATERIALES_PARED: dict[str, tuple[str, float]] = {
    "pladur": ("Pladur", 4.0),
    "ladrillo": ("Ladrillo", 8.0),
    "hormigon": ("Hormigón / carga", 15.0),
    "personalizado": ("Personalizado", 8.0),
}


def atenuacion_material(material: str) -> float:
    return MATERIALES_PARED.get(material, ("Personalizado", 8.0))[1]


@dataclass
class Medicion:
    x: float
    y: float
    signal_dbm: int
    ssid: str = ""
    bssid: str = ""
    timestamp: float = field(default_factory=time.time)
    floor_id: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "signal_dbm": self.signal_dbm,
            "ssid": self.ssid,
            "bssid": self.bssid,
            "timestamp": self.timestamp,
            "floor_id": self.floor_id,
            "notes": self.notes,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> Medicion:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            x=float(data["x"]),
            y=float(data["y"]),
            signal_dbm=int(data["signal_dbm"]),
            ssid=data.get("ssid", ""),
            bssid=data.get("bssid", ""),
            timestamp=data.get("timestamp", time.time()),
            floor_id=data.get("floor_id", ""),
            notes=data.get("notes", ""),
        )


@dataclass
class Obstaculo:
    """Segmento de pared con coeficiente de atenuación en dB."""

    x1: float
    y1: float
    x2: float
    y2: float
    material: str = "ladrillo"
    atenuacion_db: float = 8.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def desde_material(
        cls,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        material: str,
        atenuacion_db: float | None = None,
    ) -> Obstaculo:
        att = atenuacion_db if atenuacion_db is not None else atenuacion_material(material)
        return cls(x1=x1, y1=y1, x2=x2, y2=y2, material=material, atenuacion_db=att)

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "material": self.material,
            "atenuacion_db": self.atenuacion_db,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> Obstaculo:
        material = data.get("material", "ladrillo")
        att = float(data.get("atenuacion_db", MATERIALES_PARED.get(material, ("", 8.0))[1]))
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            x1=float(data["x1"]),
            y1=float(data["y1"]),
            x2=float(data["x2"]),
            y2=float(data["y2"]),
            material=material,
            atenuacion_db=att,
        )


@dataclass
class PuntoRuta:
    x: float
    y: float
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    registered: bool = False
    signal_dbm: int | None = None

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "registered": self.registered,
            "signal_dbm": self.signal_dbm,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> PuntoRuta:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            x=float(data["x"]),
            y=float(data["y"]),
            registered=bool(data.get("registered", False)),
            signal_dbm=data.get("signal_dbm"),
        )
