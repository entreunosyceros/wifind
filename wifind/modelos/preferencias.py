"""Preferencias de la aplicación."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _ruta_configuracion() -> Path:
    base = Path.home() / ".config" / "wifind"
    base.mkdir(parents=True, exist_ok=True)
    return base / "settings.json"


@dataclass
class PreferenciasApp:
    scan_interval_ms: int = 5000
    threshold_excellent: int = -50
    threshold_good: int = -60
    threshold_fair: int = -70
    threshold_weak: int = -80
    alert_threshold_dbm: int = -75
    alert_duration_sec: int = 5
    units: str = "m"  # m or ft
    theme: str = "dark"  # light or dark
    export_dir: str = ""
    survey_interval_sec: int = 3
    walk_step_m: float = 1.0
    auto_survey_advance_y: bool = True
    compare_ssids: list[str] = field(default_factory=list)
    enable_light_port_scan: bool = False
    light_port_timeout_ms: int = 400

    @property
    def thresholds(self) -> dict[str, int]:
        return {
            "excellent": self.threshold_excellent,
            "good": self.threshold_good,
            "fair": self.threshold_fair,
            "weak": self.threshold_weak,
        }

    def sufijo_longitud(self) -> str:
        return " ft" if self.units == "ft" else " m"

    def a_metros(self, value: float) -> float:
        return value * 0.3048 if self.units == "ft" else value

    def desde_metros(self, value: float) -> float:
        return value / 0.3048 if self.units == "ft" else value

    def save(self) -> None:
        path = _ruta_configuracion()
        data = asdict(self)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls) -> PreferenciasApp:
        path = _ruta_configuracion()
        if not path.exists():
            prefs = cls()
            prefs.save()
            return prefs
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                scan_interval_ms=int(data.get("scan_interval_ms", 5000)),
                threshold_excellent=int(data.get("threshold_excellent", -50)),
                threshold_good=int(data.get("threshold_good", -60)),
                threshold_fair=int(data.get("threshold_fair", -70)),
                threshold_weak=int(data.get("threshold_weak", -80)),
                alert_threshold_dbm=int(data.get("alert_threshold_dbm", -75)),
                alert_duration_sec=int(data.get("alert_duration_sec", 5)),
                units=data.get("units", "m"),
                theme=data.get("theme", "dark"),
                export_dir=data.get("export_dir", ""),
                survey_interval_sec=int(data.get("survey_interval_sec", 3)),
                walk_step_m=float(data.get("walk_step_m", 1.0)),
                auto_survey_advance_y=bool(data.get("auto_survey_advance_y", True)),
                compare_ssids=list(data.get("compare_ssids", [])),
                enable_light_port_scan=bool(data.get("enable_light_port_scan", False)),
                light_port_timeout_ms=int(data.get("light_port_timeout_ms", 400)),
            )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return cls()
