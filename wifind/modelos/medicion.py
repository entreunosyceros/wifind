"""Medición de señal, obstáculos (paredes) y puntos de acceso en el mapa."""

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


# tipo → (etiqueta UI, color hex, marcador matplotlib)
TIPOS_PUNTO_ACCESO: dict[str, tuple[str, str, str]] = {
    "router": ("Router", "#C62828", "^"),
    "ap": ("AP", "#1565C0", "^"),
    "repetidor": ("Repetidor", "#6A1B9A", "D"),
}


def etiqueta_tipo_ap(tipo: str) -> str:
    return TIPOS_PUNTO_ACCESO.get(tipo, ("AP", "#1565C0", "^"))[0]


def color_tipo_ap(tipo: str) -> str:
    return TIPOS_PUNTO_ACCESO.get(tipo, ("AP", "#1565C0", "^"))[1]


def marcador_tipo_ap(tipo: str) -> str:
    return TIPOS_PUNTO_ACCESO.get(tipo, ("AP", "#1565C0", "^"))[2]


def nombre_por_defecto_ap(tipo: str) -> str:
    return {
        "router": "Router",
        "ap": "AP Oficina",
        "repetidor": "Repetidor",
    }.get(tipo, "AP")


@dataclass
class PuntoAcceso:
    """Marcador visual de un equipo WiFi (router, AP, repetidor) en el plano."""

    x: float
    y: float
    tipo: str = "ap"
    nombre: str = "AP"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    notas: str = ""
    es_referencia: bool = False

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "tipo": self.tipo,
            "nombre": self.nombre,
            "notas": self.notas,
            "es_referencia": self.es_referencia,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> PuntoAcceso:
        tipo = data.get("tipo", "ap")
        if tipo not in TIPOS_PUNTO_ACCESO:
            tipo = "ap"
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            x=float(data["x"]),
            y=float(data["y"]),
            tipo=tipo,
            nombre=data.get("nombre") or nombre_por_defecto_ap(tipo),
            notas=data.get("notas", ""),
            es_referencia=bool(data.get("es_referencia", False)),
        )


NOMBRES_HABITACION: tuple[str, ...] = (
    "Salón",
    "Dormitorio",
    "Cocina",
    "Despacho",
    "Baño",
    "Pasillo",
    "Comedor",
    "Terraza",
)

COLORES_HABITACION: tuple[str, ...] = (
    "#42A5F5",
    "#66BB6A",
    "#FFA726",
    "#AB47BC",
    "#26A69A",
    "#EF5350",
    "#5C6BC0",
    "#8D6E63",
)


@dataclass
class Habitacion:
    """Zona rectangular/poligonal del plano (salón, dormitorio, etc.)."""

    nombre: str
    vertices: list[tuple[float, float]]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    color: str = "#42A5F5"

    @classmethod
    def desde_rectangulo(
        cls,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        nombre: str,
        color: str = "#42A5F5",
    ) -> Habitacion:
        xa, xb = min(x1, x2), max(x1, x2)
        ya, yb = min(y1, y2), max(y1, y2)
        return cls(
            nombre=nombre,
            vertices=[(xa, ya), (xb, ya), (xb, yb), (xa, yb)],
            color=color,
        )

    def centro(self) -> tuple[float, float]:
        if not self.vertices:
            return 0.0, 0.0
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        return sum(xs) / len(xs), sum(ys) / len(ys)

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "vertices": [[float(x), float(y)] for x, y in self.vertices],
            "color": self.color,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> Habitacion:
        verts_raw = data.get("vertices") or []
        vertices: list[tuple[float, float]] = []
        for v in verts_raw:
            if isinstance(v, (list, tuple)) and len(v) >= 2:
                vertices.append((float(v[0]), float(v[1])))
        if len(vertices) < 3 and all(k in data for k in ("x1", "y1", "x2", "y2")):
            return cls.desde_rectangulo(
                float(data["x1"]),
                float(data["y1"]),
                float(data["x2"]),
                float(data["y2"]),
                data.get("nombre", "Habitación"),
                data.get("color", "#42A5F5"),
            )
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            nombre=data.get("nombre", "Habitación"),
            vertices=vertices,
            color=data.get("color", "#42A5F5"),
        )
