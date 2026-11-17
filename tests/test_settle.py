from batteri.settle import load_known_offline, offline_ids, save_known_offline, settle


def dev(id, status):
    return {"id": id, "deviceStatus": status}


class Source:
    """Ger en ny lista per omhämtning och räknar anrop och väntetid."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.fetches = 0
        self.slept = []

    def refetch(self):
        self.fetches += 1
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    def run(self, first, known, **kwargs):
        return settle(first, known, self.refetch, self.slept.append, **kwargs)


def test_offline_ids_ignores_online_and_missing_id():
    raw = [dev("a", "200"), dev("b", "201"), dev("c", "203"), {"deviceStatus": "201"}]
    assert offline_ids(raw) == {"b", "c"}


def test_no_wait_when_everything_is_online():
    src = Source([dev("a", "200")])
    first = [dev("a", "200")]
    assert src.run(first, set()) is first
    assert src.fetches == 0 and src.slept == []


def test_no_wait_for_devices_that_were_offline_last_time():
    first = [dev("a", "200"), dev("gammal", "203")]
    src = Source(first)
    assert src.run(first, {"gammal"}) is first
    assert src.fetches == 0


def test_waits_until_unexpectedly_offline_device_reports_in():
    first = [dev("mac", "201"), dev("gammal", "203")]
    second = [dev("mac", "201"), dev("gammal", "203")]
    third = [dev("mac", "200"), dev("gammal", "203")]
    src = Source(second, third)
    assert src.run(first, {"gammal"}) == third
    assert src.fetches == 2 and src.slept == [2.5, 2.5]


def test_gives_up_after_max_attempts_when_device_really_is_offline():
    first = [dev("mac", "201")]
    src = Source(first)
    assert src.run(first, set(), attempts=3) == first
    assert src.fetches == 3


def test_first_run_without_state_waits_for_all_offline_devices():
    first = [dev("gammal", "203")]
    src = Source(first)
    src.run(first, None)
    assert src.fetches == 3


def test_state_roundtrip_and_broken_file(tmp_path):
    path = tmp_path / "state.json"
    assert load_known_offline(path) is None
    save_known_offline(path, [dev("a", "200"), dev("b", "201")])
    assert load_known_offline(path) == {"b"}
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    path.write_text("trasig")
    assert load_known_offline(path) is None
