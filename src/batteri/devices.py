"""Tolkar enhetsdata från Hitta (Find My) och gör den visningsbar. Ingen nätverkskod här."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Iterable

from rich.table import Table
from rich.text import Text

from .bluetooth import Accessory, BluetoothBattery

BAR_WIDTH = 10
MAX_NAME = 28
LOW = 20
MEDIUM = 50


@dataclass(frozen=True)
class Device:
    name: str
    model: str
    percent: int | None  # None = Apple rapporterar ingen batterinivå
    charging: bool
    low_power: bool
    online: bool
    family: bool  # tillhör en familjemedlem, inte det egna kontot
    note: str = ""  # extra upplysning, t.ex. att värdet kommer från Macens Bluetooth
    # Språkneutrala fält för program som läser --json (t.ex. menyradsappen):
    device_class: str = ""  # Apples enhetsklass: iPhone, iPad, Watch, MacBookPro, Accessory, Keyboard …
    source: str = "find_my"  # find_my | bluetooth | bluetooth_last_known
    left: int | None = None  # AirPods: vänster, höger och etui var för sig
    right: int | None = None
    case: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_device(raw: dict[str, Any]) -> Device:
    """Gör om en rå enhetspost från Hitta-API:t till en Device."""
    level = raw.get("batteryLevel")
    status = raw.get("batteryStatus") or "Unknown"

    percent: int | None
    if not isinstance(level, (int, float)) or isinstance(level, bool):
        percent = None
    elif status == "Unknown" and level <= 0:
        # Enheter utan batterirapport (t.ex. vissa tillbehör) skickar 0 + Unknown.
        percent = None
    else:
        percent = max(0, min(100, round(level * 100)))

    return Device(
        name=str(raw.get("name") or raw.get("deviceDisplayName") or "Okänd enhet"),
        model=str(raw.get("deviceDisplayName") or raw.get("deviceClass") or ""),
        percent=percent,
        charging=status in ("Charging", "Charged"),
        low_power=bool(raw.get("lowPowerMode")),
        online=str(raw.get("deviceStatus")) == "200",
        family=bool(raw.get("prsId")),
        device_class=str(raw.get("deviceClass") or ""),
    )


def fill_from_bluetooth(devices: Iterable[Device], bluetooth: dict[str, BluetoothBattery]) -> list[Device]:
    """Fyller i nivå från Macens Bluetooth för enheter där Hitta inte ger någon.

    Matchar på enhetsnamn. Hittas värde vinner alltid när det finns."""
    result = []
    for d in devices:
        bt = bluetooth.get(d.name)
        if d.percent is None and bt is not None and bt.percent is not None:
            source = "via Bluetooth" if bt.connected else "senast känt"
            note = ", ".join(p for p in (bt.detail, source) if p)
            d = replace(
                d,
                percent=bt.percent,
                note=note,
                online=d.online or bt.connected,
                source="bluetooth" if bt.connected else "bluetooth_last_known",
                left=bt.left,
                right=bt.right,
                case=bt.case,
            )
        result.append(d)
    return result


def add_accessories(devices: Iterable[Device], accessories: Iterable[Accessory]) -> list[Device]:
    """Lägger till Macens anslutna tillbehör som inte redan finns i listan."""
    result = list(devices)
    known = {d.name for d in result}
    for a in accessories:
        if a.name not in known:
            result.append(Device(name=a.name, model=a.kind, percent=a.percent, charging=False,
                                 low_power=False, online=True, family=False, note="via Bluetooth",
                                 device_class=a.device_class, source="bluetooth"))
    return result


def sort_devices(devices: Iterable[Device]) -> list[Device]:
    """Egna enheter först, lägst batteri överst, okänd nivå sist."""
    return sorted(
        devices,
        key=lambda d: (
            d.family,
            d.percent is None,
            d.percent if d.percent is not None else 0,
            d.name.lower(),
        ),
    )


def level_color(percent: int) -> str:
    if percent <= LOW:
        return "red"
    if percent <= MEDIUM:
        return "yellow"
    return "green"


def bar(percent: int) -> str:
    filled = round(percent / 100 * BAR_WIDTH)
    if percent > 0:
        filled = max(1, filled)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def status_text(device: Device) -> str:
    parts = []
    if device.charging:
        parts.append("laddar" if (device.percent or 0) < 100 else "fulladdad")
    if device.low_power:
        parts.append("strömsparläge")
    if device.note:
        parts.append(device.note)
    elif not device.online:
        parts.append("offline")
    return ", ".join(parts)


def build_table(devices: Iterable[Device], width: int = 100) -> Table:
    """Bygger tabellen. Bara modellkolumnen krymper (med …) i smala fönster,
    och den utelämnas helt om den inte får plats – övriga kolumner bryts aldrig."""
    devices = list(devices)
    pad = 2
    name_w = max((len(d.name) + (len(" (familj)") if d.family else 0) for d in devices), default=0)
    name_w = min(name_w, MAX_NAME)  # ett enda långt namn ska inte tränga undan resten
    status_w = max((len(status_text(d)) for d in devices), default=0)
    model_w = max((len(d.model) for d in devices), default=0)
    core = name_w + pad + BAR_WIDTH + pad + len("100 %")
    status_w = max(0, min(status_w, width - core - pad))  # status kortas hellre än att nivån trängs undan
    fixed = core + (pad + status_w if status_w else 0)
    model_w = min(model_w, width - fixed - pad)
    show_model = model_w >= 8

    table = Table(box=None, pad_edge=False, show_header=False, padding=(0, pad, 0, 0))
    table.add_column("Enhet", no_wrap=True, overflow="ellipsis", width=name_w)
    if show_model:
        table.add_column("Modell", style="dim", no_wrap=True, overflow="ellipsis", width=model_w)
    table.add_column("Nivå", no_wrap=True, width=BAR_WIDTH)
    table.add_column("Procent", justify="right", no_wrap=True, width=len("100 %"))
    table.add_column("Status", style="dim", no_wrap=True, overflow="ellipsis", width=status_w)

    def add(name, model, *rest):
        table.add_row(name, *([model] if show_model else []), *rest)

    for d in sort_devices(devices):
        name = Text(d.name, style="" if d.online else "dim")
        if d.family:
            name.append(" (familj)", style="dim")
        if d.percent is None:
            add(name, d.model, Text("·" * BAR_WIDTH, style="dim"), "–", status_text(d))
            continue
        color = level_color(d.percent) if (d.online or d.note) else "dim"
        add(
            name,
            d.model,
            Text(bar(d.percent), style=color),
            Text(f"{d.percent} %", style=color),
            status_text(d),
        )
    return table
