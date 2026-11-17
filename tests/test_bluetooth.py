from batteri.bluetooth import Accessory, BluetoothBattery, parse_accessories, parse_profiler
from batteri.devices import add_accessories, fill_from_bluetooth, parse_device, status_text

PROFILER = {
    "SPBluetoothDataType": [
        {
            "device_connected": [
                {"Magic Mouse": {"device_minorType": "Mouse"}},
                {"Lurar": {"device_batteryLevelMain": "55 %"}},
            ],
            "device_not_connected": [
                {
                    "Mina AirPods": {
                        "device_batteryLevelCase": "100\xa0%",
                        "device_batteryLevelLeft": "70\xa0%",
                        "device_batteryLevelRight": "85\xa0%",
                    }
                }
            ],
        }
    ]
}


def device(name, **overrides):
    raw = {"name": name, "deviceDisplayName": "AirPods", "batteryLevel": 0.0,
           "batteryStatus": "Unknown", "deviceStatus": "201"}
    return parse_device({**raw, **overrides})


def test_parse_profiler_reads_levels_and_skips_devices_without_battery():
    bt = parse_profiler(PROFILER)
    assert set(bt) == {"Lurar", "Mina AirPods"}
    pods = bt["Mina AirPods"]
    assert (pods.left, pods.right, pods.case, pods.connected) == (70, 85, 100, False)
    assert pods.percent == 70  # lägsta snäckan, inte etuiet
    assert pods.detail == "V70 H85 etui100"
    assert bt["Lurar"].percent == 55 and bt["Lurar"].connected and bt["Lurar"].detail == ""


def test_parse_profiler_tolerates_empty_input():
    assert parse_profiler({}) == {}
    assert parse_profiler({"SPBluetoothDataType": [{}]}) == {}


def test_case_only_reading_is_used_when_buds_missing():
    assert BluetoothBattery(connected=False, case=40).percent == 40


def test_fill_marks_stale_value_for_disconnected_device():
    [d] = fill_from_bluetooth([device("Mina AirPods")], parse_profiler(PROFILER))
    assert d.percent == 70 and not d.online
    assert status_text(d) == "V70 H85 etui100, senast känt"


def test_fill_connected_device_counts_as_online():
    [d] = fill_from_bluetooth([device("Lurar")], parse_profiler(PROFILER))
    assert d.percent == 55 and d.online and status_text(d) == "via Bluetooth"


def test_find_my_value_wins_and_unmatched_devices_are_untouched():
    known = device("Mina AirPods", batteryLevel=0.3, batteryStatus="NotCharging", deviceStatus="200")
    other = device("Annan")
    out = fill_from_bluetooth([known, other], parse_profiler(PROFILER))
    assert out[0].percent == 30 and out[0].note == ""
    assert out[1].percent is None and status_text(out[1]) == "offline"


ACC_PROFILER = {
    "SPBluetoothDataType": [
        {
            "device_connected": [
                {"Magic Mouse": {"device_address": "AA:BB:CC:00:00:01", "device_minorType": "Mouse"}},
                {"Mitt tangentbord": {"device_address": "AA:BB:CC:00:00:02", "device_minorType": "Keyboard"}},
                {"iPhone": {"device_address": "AA:BB:CC:00:00:03"}},
            ]
        }
    ]
}
ACC_IOREG = [
    {"BatteryPercent": 44, "DeviceAddress": "aa-bb-cc-00-00-01", "Product": ""},
    {"IORegistryEntryChildren": [{"BatteryPercent": 92, "DeviceAddress": "aa-bb-cc-00-00-02"}]},
    {"BatteryPercent": 10, "DeviceAddress": "dd-ee-ff-00-00-09"},
    {"BatteryPercent": 50},  # utan adress: går inte att namnge, hoppas över
]


def test_accessories_are_matched_to_names_by_address():
    acc = parse_accessories(ACC_PROFILER, ACC_IOREG)
    assert acc == [
        Accessory("Magic Mouse", "Mus", 44),
        Accessory("Mitt tangentbord", "Tangentbord", 92),
        Accessory("Bluetooth-tillbehör", "", 10),
    ]


def test_accessories_tolerate_empty_input():
    assert parse_accessories({}, []) == []
    assert parse_accessories(ACC_PROFILER, []) == []


def test_add_accessories_appends_without_duplicating_find_my_devices():
    existing = device("Magic Mouse", batteryLevel=0.3, batteryStatus="NotCharging")
    out = add_accessories([existing], parse_accessories(ACC_PROFILER, ACC_IOREG)[:2])
    assert [d.name for d in out] == ["Magic Mouse", "Mitt tangentbord"]
    assert out[0].percent == 30
    kb = out[1]
    assert (kb.percent, kb.model, kb.online) == (92, "Tangentbord", True)
    assert status_text(kb) == "via Bluetooth"
