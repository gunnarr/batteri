"""Inloggningsflödet mot iCloud, skilt från hur frågorna ställs.

Samma flöde används av `batteri login` i terminalen och av `batteri login --stdio`, som
låter ett annat program (menyradsappen) sköta dialogen via JSON-rader på stdin/stdout.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, TextIO

OK = "ok"
NEEDS_CODE = "needs_code"
ERROR = "error"


@dataclass(frozen=True)
class Result:
    state: str  # ok | needs_code | error
    code: str = ""  # bad_credentials | bad_code | security_key | unsupported_2sa | failed | bad_request
    message: str = ""  # teknisk detalj, inte avsedd att visas ordagrant

    def to_json(self) -> str:
        return json.dumps({k: v for k, v in asdict(self).items() if v})


class LoginFlow:
    """Håller pyicloud-tjänsten vid liv mellan lösenord och tvåfaktorskod."""

    def __init__(self, make_service: Callable[[str, str], Any], on_success: Callable[[str], None]) -> None:
        self._make_service = make_service
        self._on_success = on_success
        self._api: Any = None
        self._apple_id = ""

    def start(self, apple_id: str, password: str) -> Result:
        from pyicloud.exceptions import PyiCloudException, PyiCloudFailedLoginException

        self._apple_id = apple_id
        try:
            self._api = self._make_service(apple_id, password)
            if self._api.requires_2fa:
                if self._api.security_key_names:
                    return Result(ERROR, "security_key")
                self._api.request_2fa_code()
                return Result(NEEDS_CODE)
            if self._api.requires_2sa:
                return Result(ERROR, "unsupported_2sa")
        except PyiCloudFailedLoginException as e:
            return Result(ERROR, "bad_credentials", str(e))
        except PyiCloudException as e:
            return Result(ERROR, "failed", str(e))
        return self._done()

    def submit_code(self, code: str) -> Result:
        from pyicloud.exceptions import PyiCloudException

        if self._api is None:
            return Result(ERROR, "bad_request", "submit_code before start")
        try:
            if not self._api.validate_2fa_code(code):
                # Fel kod: be om en ny, så att användaren kan försöka igen.
                self._api.request_2fa_code()
                return Result(NEEDS_CODE, "bad_code")
            if not self._api.is_trusted_session:
                self._api.trust_session()
        except PyiCloudException as e:
            return Result(ERROR, "failed", str(e))
        return self._done()

    def _done(self) -> Result:
        self._on_success(self._apple_id)
        return Result(OK)


def run_stdio(flow: LoginFlow, stdin: TextIO, stdout: TextIO) -> int:
    """Protokoll, en JSON-rad åt gången:

        in : {"apple_id": "...", "password": "..."}
        ut : {"state": "ok"} | {"state": "needs_code"} | {"state": "error", "code": "..."}
        in : {"code": "123456"}            (upprepas så länge svaret är needs_code)
        ut : {"state": "ok"} | {"state": "needs_code", "code": "bad_code"} | {"state": "error", ...}

    Lösenordet går bara via stdin, aldrig som argument, och skrivs aldrig ut."""

    def read() -> dict[str, Any] | None:
        line = stdin.readline()
        if not line:
            return None
        try:
            value = json.loads(line)
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    def write(result: Result) -> None:
        stdout.write(result.to_json() + "\n")
        stdout.flush()

    request = read()
    if request is None:
        return 1
    apple_id, password = request.get("apple_id"), request.get("password")
    if not isinstance(apple_id, str) or not isinstance(password, str) or not apple_id or not password:
        write(Result(ERROR, "bad_request", "expected apple_id and password"))
        return 1

    result = flow.start(apple_id.strip(), password)
    write(result)
    while result.state == NEEDS_CODE:
        request = read()
        if request is None:
            return 1  # motparten avbröt
        code = request.get("code")
        if not isinstance(code, str) or not code.strip():
            result = Result(NEEDS_CODE, "bad_code")
        else:
            result = flow.submit_code(code.strip())
        write(result)
    return 0 if result.state == OK else 1
