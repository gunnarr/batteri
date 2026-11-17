from rich.console import Console

from batteri.devices import bar, build_table, level_color, parse_device, sort_devices, status_text

IPHONE = {
    "name": "Min iPhone",
    "deviceDisplayName": "iPhone 16 Pro",
    "deviceClass": "iPhone",
    "batteryLevel": 0.4199999,
    "batteryStatus": "NotCharging",
    "deviceStatus": "200",
    "lowPowerMode": False,
    "prsId": None,
}


def make(**overrides):
    return parse_device({**IPHONE, **overrides})


def test_parses_level_as_rounded_percent():
    d = make()
    assert (d.name, d.model, d.percent) == ("Min iPhone", "iPhone 16 Pro", 42)
    assert d.online and not d.charging and not d.family


def test_unknown_status_with_zero_level_means_no_reading():
    assert make(batteryLevel=0.0, batteryStatus="Unknown").percent is None
    assert make(batteryLevel=None).percent is None
    assert make(batteryLevel=0.0, batteryStatus=None).percent is None


def test_real_zero_percent_is_kept():
    assert make(batteryLevel=0.0, batteryStatus="NotCharging").percent == 0


def test_unknown_status_with_level_keeps_level():
    assert make(batteryLevel=0.8, batteryStatus="Unknown").percent == 80


def test_level_is_clamped():
    assert make(batteryLevel=1.2).percent == 100
    assert make(batteryLevel=-0.1, batteryStatus="NotCharging").percent == 0


def test_charging_offline_family_flags():
    d = make(batteryStatus="Charging", deviceStatus="201", prsId="abc", lowPowerMode=True)
    assert d.charging and not d.online and d.family and d.low_power
    assert status_text(d) == "laddar, strömsparläge, offline"
    assert status_text(make(batteryLevel=1.0, batteryStatus="Charged")) == "fulladdad"
    assert status_text(make()) == ""


def test_missing_fields_do_not_crash():
    d = parse_device({})
    assert d.name == "Okänd enhet" and d.percent is None and not d.online


def test_sort_own_first_lowest_first_unknown_last():
    devices = [
        make(name="Familj låg", batteryLevel=0.05, prsId="x"),
        make(name="Okänd", batteryLevel=None),
        make(name="Hög", batteryLevel=0.9),
        make(name="Låg", batteryLevel=0.1),
    ]
    assert [d.name for d in sort_devices(devices)] == ["Låg", "Hög", "Okänd", "Familj låg"]


def test_bar_and_color():
    assert bar(0) == "░" * 10
    assert bar(3) == "█" + "░" * 9  # visar alltid minst ett steg när det finns laddning
    assert bar(50) == "█" * 5 + "░" * 5
    assert bar(100) == "█" * 10
    assert [level_color(p) for p in (20, 21, 50, 51)] == ["red", "yellow", "yellow", "green"]


def test_table_renders_all_devices():
    console = Console(width=100, record=True, force_terminal=False)
    console.print(build_table([make(), make(name="AirPods", batteryLevel=None, prsId="x")]))
    out = console.export_text()
    assert "Min iPhone" in out and "42 %" in out
    assert "AirPods (familj)" in out and "–" in out


def render(devices, width):
    console = Console(width=width, record=True, force_terminal=False)
    console.print(build_table(devices, width))
    return console.export_text().splitlines()


def test_narrow_width_truncates_only_model_and_never_wraps():
    devices = [
        make(name="Annas Apple Watch Ultra 2", deviceDisplayName="MacBook Pro (14-inch, M5 Pro)", batteryLevel=1.0),
        make(name="Hörlurar", batteryLevel=None, deviceStatus="201"),
    ]
    lines = render(devices, 70)
    assert len(lines) == 2
    assert "Annas Apple Watch Ultra 2" in lines[0] and "100 %" in lines[0] and "█" * 10 in lines[0]
    assert "…" in lines[0] and "offline" in lines[1]


def test_very_narrow_width_drops_model_column():
    lines = render([make(name="Annas Apple Watch Ultra 2", batteryLevel=1.0)], 50)
    assert len(lines) == 1
    assert "iPhone 16 Pro" not in lines[0] and "100 %" in lines[0]


def test_long_name_is_truncated_so_status_still_fits():
    long = make(name="Magic Keyboard med Touch ID och numeriskt tangentbord", deviceStatus="201")
    [line] = render([long], 80)
    assert "Magic Keyboard med Touch ID" in line and "…" in line
    assert "42 %" in line and "offline" in line
