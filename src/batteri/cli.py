"""batteri – batteristatus för alla enheter på Apple-kontot, hämtat från Hitta (Find My)."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
import time
import tomllib
from pathlib import Path

from rich.console import Console

from .bluetooth import read_local
from .settle import load_known_offline, save_known_offline, settle
from .devices import add_accessories, build_table, fill_from_bluetooth, parse_device, sort_devices

console = Console()
err = Console(stderr=True)


def home() -> Path:
    return Path(os.environ.get("BATTERI_HOME", "~/.config/batteri")).expanduser()


def config_path() -> Path:
    return home() / "config.toml"


def session_dir() -> Path:
    return home() / "session"


def load_apple_id() -> str | None:
    try:
        with config_path().open("rb") as f:
            return tomllib.load(f).get("apple_id")
    except FileNotFoundError:
        return None


def save_apple_id(apple_id: str) -> None:
    home().mkdir(parents=True, exist_ok=True)
    home().chmod(0o700)
    path = config_path()
    path.write_text(f"apple_id = {json.dumps(apple_id)}\n")
    path.chmod(0o600)


def fail(message: str) -> int:
    err.print(f"[red]{message}[/red]")
    return 1


def cmd_login(args: argparse.Namespace) -> int:
    from pyicloud import PyiCloudService
    from pyicloud.exceptions import PyiCloudException

    apple_id = args.apple_id or load_apple_id() or input("Apple-ID (e-post): ").strip()
    if not apple_id:
        return fail("Inget Apple-ID angivet.")

    if args.op:
        # Lösenordet hämtas direkt från 1Password och skrivs aldrig ut eller sparas.
        result = subprocess.run(["op", "read", args.op], capture_output=True, text=True)
        if result.returncode != 0:
            return fail(f"Kunde inte läsa lösenordet från 1Password: {result.stderr.strip()}")
        password = result.stdout.rstrip("\n")
    else:
        password = getpass.getpass(f"Lösenord för {apple_id}: ")

    try:
        api = PyiCloudService(
            apple_id,
            password,
            cookie_directory=str(session_dir()),
            with_family=False,
            refresh_interval=None,
        )
        if api.requires_2fa:
            if api.security_key_names:
                return fail("Kontot kräver säkerhetsnyckel, vilket batteri inte stöder.")
            api.request_2fa_code()
            code = input("Sexsiffrig kod från en av dina enheter: ").strip()
            if not api.validate_2fa_code(code):
                return fail("Koden godkändes inte.")
            if not api.is_trusted_session and not api.trust_session():
                err.print("[yellow]Sessionen kunde inte markeras som betrodd – du kan behöva logga in igen snart.[/yellow]")
        elif api.requires_2sa:
            return fail("Kontot använder äldre tvåstegsverifiering, vilket batteri inte stöder.")
    except PyiCloudException as e:
        return fail(f"Inloggningen misslyckades: {e}")

    save_apple_id(apple_id)
    console.print("[green]Inloggad.[/green] Kör [bold]batteri[/bold] för att se batteristatus.")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    from pyicloud import PyiCloudService
    from pyicloud.exceptions import PyiCloudException, PyiCloudFailedLoginException

    apple_id = load_apple_id()
    if not apple_id:
        return fail("Inte inloggad än. Kör: batteri login")

    try:
        # authenticate=False + inget lösenord: visningen kan bara återanvända den
        # sparade sessionen och kan aldrig själv starta en ny inloggning/2FA-fråga.
        api = PyiCloudService(
            apple_id,
            None,
            cookie_directory=str(session_dir()),
            with_family=args.familj,
            refresh_interval=None,
            authenticate=False,
        )
        try:
            api.authenticate()
        except PyiCloudFailedLoginException:
            return fail("Sessionen har gått ut. Kör: batteri login")
        if api.requires_2fa or api.requires_2sa:
            return fail("Sessionen har gått ut. Kör: batteri login")
        manager = api.devices

        def snapshot() -> list[dict]:
            return [d.data for d in manager.devices.values()]

        def refetch() -> list[dict]:
            manager.refresh(locate=False)
            return snapshot()

        def wait(seconds: float) -> None:
            with err.status("Väntar på att enheter ska svara …"):
                time.sleep(seconds)

        state = home() / "state.json"
        raw = settle(snapshot(), load_known_offline(state), refetch, wait)
        save_known_offline(state, raw)
    except PyiCloudException as e:
        return fail(f"Kunde inte hämta enheter från Hitta: {e}")

    if args.raw:
        print(json.dumps(raw, ensure_ascii=False, indent=2, default=str))
        return 0

    devices = [parse_device(r) for r in raw]
    bluetooth, accessories = read_local()
    devices = add_accessories(fill_from_bluetooth(devices, bluetooth), accessories)
    devices = sort_devices(devices)
    if args.json:
        print(json.dumps([d.to_dict() for d in devices], ensure_ascii=False, indent=2))
    else:
        console.print(build_table(devices, console.width))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="batteri",
        description="Visa batteristatus för alla enheter på ditt Apple-konto (från Hitta).",
    )
    parser.add_argument("--familj", action="store_true", help="ta med familjemedlemmars enheter")
    parser.add_argument("--json", action="store_true", help="skriv ut som JSON")
    parser.add_argument("--raw", action="store_true", help="skriv ut Apples rådata (felsökning)")
    sub = parser.add_subparsers(dest="command")
    login = sub.add_parser("login", help="logga in på iCloud (behövs igen när sessionen gått ut)")
    login.add_argument("--apple-id", help="Apple-ID, om det inte redan är sparat")
    login.add_argument("--op", metavar="REF", help="1Password-referens till lösenordet, t.ex. op://Personal/Apple/password")

    args = parser.parse_args(argv)
    try:
        return cmd_login(args) if args.command == "login" else cmd_show(args)
    except KeyboardInterrupt:
        return 130
    except EOFError:
        err.print()
        return fail("Inloggningen behöver ett interaktivt terminalfönster. Kör batteri login i Terminal.")


if __name__ == "__main__":
    sys.exit(main())
