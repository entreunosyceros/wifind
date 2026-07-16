"""Sesión de trabajo WiFind (.wifind)."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from wifind import __app_name__, __version__
from wifind.modelos.medicion import Habitacion, Medicion, Obstaculo, PuntoAcceso, PuntoRuta
from wifind.modelos.instantanea_escaneo import InstantaneaEscaneo


@dataclass
class CalibracionPlanta:
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    real_length_m: float = 0.0
    pixels_per_meter: float = 0.0

    def a_dict(self) -> dict:
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "real_length_m": self.real_length_m,
            "pixels_per_meter": self.pixels_per_meter,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> CalibracionPlanta:
        return cls(
            x1=float(data.get("x1", 0)),
            y1=float(data.get("y1", 0)),
            x2=float(data.get("x2", 0)),
            y2=float(data.get("y2", 0)),
            real_length_m=float(data.get("real_length_m", 0)),
            pixels_per_meter=float(data.get("pixels_per_meter", 0)),
        )


@dataclass
class NivelPlanta:
    name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    x_max: float = 10.0
    y_max: float = 10.0
    floor_plan_path: str | None = None
    floor_plan_asset: str | None = None
    measurements: list[Medicion] = field(default_factory=list)
    obstaculos: list[Obstaculo] = field(default_factory=list)
    waypoints: list[PuntoRuta] = field(default_factory=list)
    access_points: list[PuntoAcceso] = field(default_factory=list)
    habitaciones: list[Habitacion] = field(default_factory=list)
    calibration: CalibracionPlanta = field(default_factory=CalibracionPlanta)
    target_ssids: list[str] = field(default_factory=list)

    def a_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "x_max": self.x_max,
            "y_max": self.y_max,
            "floor_plan_path": self.floor_plan_path,
            "floor_plan_asset": self.floor_plan_asset,
            "measurements": [m.a_dict() for m in self.measurements],
            "obstaculos": [o.a_dict() for o in self.obstaculos],
            "waypoints": [w.a_dict() for w in self.waypoints],
            "access_points": [ap.a_dict() for ap in self.access_points],
            "habitaciones": [h.a_dict() for h in self.habitaciones],
            "calibration": self.calibration.a_dict(),
            "target_ssids": self.target_ssids,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> NivelPlanta:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Planta baja"),
            x_max=float(data.get("x_max", 10)),
            y_max=float(data.get("y_max", 10)),
            floor_plan_path=data.get("floor_plan_path"),
            floor_plan_asset=data.get("floor_plan_asset"),
            measurements=[Medicion.desde_dict(m) for m in data.get("measurements", [])],
            obstaculos=[Obstaculo.desde_dict(o) for o in data.get("obstaculos", [])],
            waypoints=[PuntoRuta.desde_dict(w) for w in data.get("waypoints", [])],
            access_points=[PuntoAcceso.desde_dict(a) for a in data.get("access_points", [])],
            habitaciones=[Habitacion.desde_dict(h) for h in data.get("habitaciones", [])],
            calibration=CalibracionPlanta.desde_dict(data.get("calibration", {})),
            target_ssids=list(data.get("target_ssids", [])),
        )


@dataclass
class HistorialIntensidad:
    ssid: str = ""
    timestamps: list[float] = field(default_factory=list)
    values_dbm: list[int] = field(default_factory=list)

    def a_dict(self) -> dict:
        return {
            "ssid": self.ssid,
            "timestamps": self.timestamps,
            "values_dbm": self.values_dbm,
        }

    @classmethod
    def desde_dict(cls, data: dict) -> HistorialIntensidad:
        return cls(
            ssid=data.get("ssid", ""),
            timestamps=[float(t) for t in data.get("timestamps", [])],
            values_dbm=[int(v) for v in data.get("values_dbm", [])],
        )


VERSION_SESION = 1


@dataclass
class SesionApp:
    name: str = "Nueva sesión"
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    floors: list[NivelPlanta] = field(default_factory=list)
    planta_activa_id: str = ""
    scan_history: list[InstantaneaEscaneo] = field(default_factory=list)
    intensity: HistorialIntensidad = field(default_factory=HistorialIntensidad)
    file_path: str | None = None

    def __post_init__(self) -> None:
        if not self.floors:
            floor = NivelPlanta(name="Planta baja")
            self.floors = [floor]
            self.planta_activa_id = floor.id

    @property
    def planta_activa(self) -> NivelPlanta:
        for floor in self.floors:
            if floor.id == self.planta_activa_id:
                return floor
        return self.floors[0]

    def touch(self) -> None:
        self.modified_at = time.time()

    def anadir_planta(self, name: str) -> NivelPlanta:
        floor = NivelPlanta(name=name)
        self.floors.append(floor)
        self.planta_activa_id = floor.id
        self.touch()
        return floor

    def a_dict(self) -> dict:
        return {
            "version": VERSION_SESION,
            "app": __app_name__,
            "app_version": __version__,
            "name": self.name,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "planta_activa_id": self.planta_activa_id,
            "floors": [f.a_dict() for f in self.floors],
            "scan_history": [s.a_dict() for s in self.scan_history],
            "intensity": self.intensity.a_dict(),
        }

    @classmethod
    def desde_dict(cls, data: dict) -> SesionApp:
        floors = [NivelPlanta.desde_dict(f) for f in data.get("floors", [])]
        session = cls(
            name=data.get("name", "Sesión"),
            created_at=float(data.get("created_at", time.time())),
            modified_at=float(data.get("modified_at", time.time())),
            floors=floors or [],
            planta_activa_id=data.get("planta_activa_id", ""),
            scan_history=[InstantaneaEscaneo.desde_dict(s) for s in data.get("scan_history", [])],
            intensity=HistorialIntensidad.desde_dict(data.get("intensity", {})),
        )
        if not session.planta_activa_id and session.floors:
            session.planta_activa_id = session.floors[0].id
        return session

    def save(self, path: Path) -> None:
        path = Path(path)
        if path.suffix != ".wifind":
            path = path.with_suffix(".wifind")
        assets_dir = path.parent / f"{path.stem}_assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        for floor in self.floors:
            if floor.floor_plan_path and Path(floor.floor_plan_path).is_file():
                src = Path(floor.floor_plan_path)
                dest = assets_dir / f"{floor.id}{src.suffix}"
                if src.resolve() != dest.resolve():
                    shutil.copy2(src, dest)
                floor.floor_plan_asset = dest.name

        data = self.a_dict()
        for floor_data, floor in zip(data["floors"], self.floors, strict=True):
            if floor.floor_plan_asset:
                floor_data["floor_plan_asset"] = floor.floor_plan_asset
                floor_data["floor_plan_path"] = None

        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.file_path = str(path)
        self.touch()

    @classmethod
    def load(cls, path: Path) -> SesionApp:
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        session = cls.desde_dict(data)
        session.file_path = str(path)
        assets_dir = path.parent / f"{path.stem}_assets"
        for floor in session.floors:
            if floor.floor_plan_asset and assets_dir.exists():
                asset = assets_dir / floor.floor_plan_asset
                if asset.is_file():
                    floor.floor_plan_path = str(asset)
        return session

    @classmethod
    def new(cls) -> SesionApp:
        return cls()
