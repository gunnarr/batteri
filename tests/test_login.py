import io
import json

from pyicloud.exceptions import PyiCloudAPIResponseException, PyiCloudFailedLoginException

from batteri.login import LoginFlow, Result, run_stdio


class FakeService:
    def __init__(self, requires_2fa=True, valid_code="123456", security_keys=None, requires_2sa=False):
        self.requires_2fa = requires_2fa
        self.requires_2sa = requires_2sa
        self.security_key_names = security_keys
        self.valid_code = valid_code
        self.code_requests = 0
        self.is_trusted_session = False
        self.trusted = False

    def request_2fa_code(self):
        self.code_requests += 1

    def validate_2fa_code(self, code):
        return code == self.valid_code

    def trust_session(self):
        self.trusted = True
        return True


def flow_with(service=None, error=None):
    saved, seen = [], []

    def make(apple_id, password):
        seen.append((apple_id, password))
        if error:
            raise error
        return service

    return LoginFlow(make, saved.append), saved, seen


def test_two_factor_happy_path_saves_apple_id_only_after_code():
    service = FakeService()
    flow, saved, seen = flow_with(service)
    assert flow.start("a@example.com", "hemligt") == Result("needs_code")
    assert saved == [] and service.code_requests == 1
    assert flow.submit_code("123456") == Result("ok")
    assert saved == ["a@example.com"] and service.trusted
    assert seen == [("a@example.com", "hemligt")]


def test_wrong_code_requests_a_new_one_and_allows_retry():
    service = FakeService()
    flow, saved, _ = flow_with(service)
    flow.start("a@example.com", "x")
    assert flow.submit_code("000000") == Result("needs_code", "bad_code")
    assert service.code_requests == 2 and saved == []
    assert flow.submit_code("123456").state == "ok"


def test_login_without_two_factor_is_ok_directly():
    flow, saved, _ = flow_with(FakeService(requires_2fa=False))
    assert flow.start("a@example.com", "x") == Result("ok")
    assert saved == ["a@example.com"]


def test_error_cases_never_save():
    for service, error, code in (
        (None, PyiCloudFailedLoginException("nej"), "bad_credentials"),
        (None, PyiCloudAPIResponseException("trasigt"), "failed"),
        (FakeService(security_keys=["YubiKey"]), None, "security_key"),
        (FakeService(requires_2fa=False, requires_2sa=True), None, "unsupported_2sa"),
    ):
        flow, saved, _ = flow_with(service, error)
        result = flow.start("a@example.com", "x")
        assert (result.state, result.code) == ("error", code)
        assert saved == []


def test_submit_code_before_start_is_rejected():
    flow, _, _ = flow_with(FakeService())
    assert flow.submit_code("123456").code == "bad_request"


def stdio(flow, *lines):
    out = io.StringIO()
    status = run_stdio(flow, io.StringIO("".join(line + "\n" for line in lines)), out)
    return status, [json.loads(line) for line in out.getvalue().splitlines()]


def test_stdio_full_conversation():
    flow, saved, _ = flow_with(FakeService())
    status, replies = stdio(
        flow,
        json.dumps({"apple_id": " a@example.com ", "password": "pw"}),
        json.dumps({"code": "111111"}),
        json.dumps({"code": " 123456 "}),
    )
    assert status == 0
    assert replies == [{"state": "needs_code"}, {"state": "needs_code", "code": "bad_code"}, {"state": "ok"}]
    assert saved == ["a@example.com"]


def test_stdio_never_echoes_the_password():
    flow, _, _ = flow_with(None, PyiCloudFailedLoginException("fel"))
    status, replies = stdio(flow, json.dumps({"apple_id": "a@example.com", "password": "superhemligt"}))
    assert status == 1 and replies[0]["code"] == "bad_credentials"
    assert "superhemligt" not in json.dumps(replies)


def test_stdio_rejects_bad_requests_and_handles_hangup():
    flow, _, seen = flow_with(FakeService())
    assert stdio(flow, "inte json")[1] == [{"state": "error", "code": "bad_request", "message": "expected apple_id and password"}]
    assert seen == []
    assert stdio(flow)[0] == 1  # ingen indata alls
    # Motparten lägger på efter lösenordet: avslutas utan att spara.
    flow, saved, _ = flow_with(FakeService())
    status, replies = stdio(flow, json.dumps({"apple_id": "a@example.com", "password": "pw"}))
    assert status == 1 and replies == [{"state": "needs_code"}] and saved == []


def test_stdio_empty_code_asks_again_without_calling_apple():
    service = FakeService()
    flow, _, _ = flow_with(service)
    _, replies = stdio(flow, json.dumps({"apple_id": "a@example.com", "password": "pw"}), json.dumps({"code": ""}))
    assert replies[-1] == {"state": "needs_code", "code": "bad_code"}
    assert service.code_requests == 1
