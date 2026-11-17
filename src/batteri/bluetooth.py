"""Batterinivåer som den här Macen själv känner till via Bluetooth (t.ex. AirPods).

Hitta-tjänsten på webben lämnar inte ut batterinivå för AirPods, men macOS sparar det
värde Macen senast såg. För en enhet som inte är ansluten just nu kan värdet vara gammalt.
"""

from __future__ import annotations

import json
import plistlib
import re
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BluetoothBattery:
    connected: bool
    left: int | None = None
    right: int | None = None
    case: int | None = None
    main: int | None = None  # enheter med ett enda batteri

    @property
    def percent(self) -> int | None:
        """Lägsta nivån av det man faktiskt använder (öronsnäckorna, inte etuiet)."""
        buds = [v for v in (self.left, self.right, self.main) if v is not None]
        if buds:
            return min(buds)
        return self.case

    @property
    def detail(self) -> str:
        parts = []
        if self.left is not None:
            parts.append(f"V{self.left}")
        if self.right is not None:
            parts.append(f"H{self.right}")
        if self.case is not None and (self.left is not None or self.right is not None):
            parts.append(f"etui{self.case}")
        return " ".join(parts)


def _percent(value: Any) -> int | None:
    match = re.search(r"\d+", str(value)) if value is not None else None
    return max(0, min(100, int(match.group()))) if match else None


def parse_profiler(data: dict[str, Any]) -> dict[str, BluetoothBattery]:
    """Plockar ut batterinivåer per enhetsnamn ur `system_profiler SPBluetoothDataType -json`."""
    result: dict[str, BluetoothBattery] = {}
    for section in data.get("SPBluetoothDataType") or []:
        for key, connected in (("device_connected", True), ("device_not_connected", False)):
            for item in section.get(key) or []:
                for name, props in item.items():
                    battery = BluetoothBattery(
                        connected=connected,
                        left=_percent(props.get("device_batteryLevelLeft")),
                        right=_percent(props.get("device_batteryLevelRight")),
                        case=_percent(props.get("device_batteryLevelCase")),
                        main=_percent(props.get("device_batteryLevelMain")),
                    )
                    if battery.percent is not None:
                        result[name] = battery
    return result


@dataclass(frozen=True)
class Accessory:
    """Anslutet tillbehör med eget batteri, t.ex. tangentbord eller mus."""

    name: str
    kind: str
    percent: int
    device_class: str = ""  # macOS egen benämning, oöversatt: Keyboard, Mouse …


KINDS = {"Keyboard": "Tangentbord", "Mouse": "Mus", "Trackpad": "Styrplatta", "Headphones": "Hörlurar"}


def _address(value: Any) -> str:
    return re.sub(r"[^0-9a-f]", "", str(value).lower())


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for child in node.values():
            yield from _walk(child)
    elif isinstance(node, list):
        for child in node:
            yield from _walk(child)


def parse_accessories(profiler: dict[str, Any], ioreg: Any) -> list[Accessory]:
    """Parar ihop batterinivåer ur `ioreg -r -k BatteryPercent -a` med namn ur system_profiler.

    ioreg har nivån men inget namn; system_profiler har namnet. Bluetooth-adressen binder ihop dem."""
    names: dict[str, tuple[str, str]] = {}
    for section in profiler.get("SPBluetoothDataType") or []:
        for item in section.get("device_connected") or []:
            for name, props in item.items():
                if props.get("device_address"):
                    names[_address(props["device_address"])] = (name, str(props.get("device_minorType") or ""))

    result: dict[str, Accessory] = {}
    for node in _walk(ioreg):
        percent, address = node.get("BatteryPercent"), node.get("DeviceAddress")
        if isinstance(percent, bool) or not isinstance(percent, int) or not address:
            continue
        key = _address(address)
        name, kind = names.get(key, ("Bluetooth-tillbehör", ""))
        result[key] = Accessory(name=name, kind=KINDS.get(kind, kind), percent=max(0, min(100, percent)),
                                device_class=kind)
    return list(result.values())


def _run(command: list[str]) -> bytes:
    return subprocess.run(command, capture_output=True, timeout=15).stdout


def read_local() -> tuple[dict[str, BluetoothBattery], list[Accessory]]:
    """Läser Macens Bluetooth-uppgifter. Ger tomma svar om det inte går."""
    try:
        profiler = json.loads(_run(["/usr/sbin/system_profiler", "SPBluetoothDataType", "-json"]))
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}, []
    try:
        out = _run(["/usr/sbin/ioreg", "-r", "-k", "BatteryPercent", "-a"])
        ioreg = plistlib.loads(out) if out.strip() else []
    except (OSError, subprocess.SubprocessError, ValueError, plistlib.InvalidFileException):
        ioreg = []
    return parse_profiler(profiler), parse_accessories(profiler, ioreg)
