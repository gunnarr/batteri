# batteri

Batteristatus för alla dina Apple-enheter, direkt i terminalen på Macen.

```
$ batteri
Magic Mouse              ████░░░░░░   44 %  via Bluetooth
Annas iPhone             ██████░░░░   61 %  strömsparläge
MacBook Pro              ████████░░   78 %
Annas Apple Watch        █████████░   93 %  laddar
Annas AirPods Pro        ██████████  100 %  V100 H100 etui100, senast känt
Gamla iPaden             ··········      –  offline
```

Appen Hitta vet hur mycket batteri som finns kvar i telefonen, klockan, surfplattan och
datorn, men visar det bara som en liten ikon per enhet. `batteri` hämtar samma uppgifter
och visar dem i procent, lägst nivå överst.

*In English: a small macOS command-line tool that lists the battery level of every device
on your Apple account, using the same data as Find My. The interface is in Swedish.*

## Kom igång

Du behöver en Mac och [uv](https://docs.astral.sh/uv/). Saknar du uv:

```
brew install uv
```

Installera och kör:

```
uv tool install git+https://github.com/gunnarr/batteri
batteri
```

Första gången frågar `batteri` efter ditt Apple-ID, ditt lösenord och den sexsiffriga kod
som dyker upp på dina enheter, och visar sedan listan. Därefter räcker det att skriva
`batteri`. När inloggningen så småningom gått ut frågar den igen.

## Kommandon

| Kommando | Gör |
|---|---|
| `batteri` | Visar batteristatus för dina enheter |
| `batteri --familj` | Tar med familjemedlemmars enheter |
| `batteri --json` | Samma uppgifter som JSON, för skript |
| `batteri --raw` | Apples rådata, för felsökning (innehåller positioner) |
| `batteri login` | Loggar in på iCloud (sker annars automatiskt vid behov) |
| `batteri login --op op://valv/objekt/password` | Läser lösenordet från 1Password i stället för att fråga |

Uppdatera med `uv tool upgrade batteri`, avinstallera med `uv tool uninstall batteri`.

## Varifrån uppgifterna kommer

- **Hitta.** iPhone, iPad, Apple Watch och Mac hämtas från samma tjänst som
  icloud.com/find använder, via biblioteket [pyicloud](https://github.com/timlaing/pyicloud).
- **Macens Bluetooth.** Hitta lämnar inte ut batterinivå för AirPods. Där visas i stället
  det värde Macen såg senast hörlurarna var anslutna, märkt "senast känt". Det kan vara
  gammalt. Är de anslutna till Macen just nu står det "via Bluetooth" och värdet är aktuellt.
- **Anslutna tillbehör.** Tangentbord, mus och styrplatta som är anslutna till Macen visas
  med aktuell nivå.

Enheter som är avstängda eller saknar batterirapport visas med "–".

## Säkerhet och integritet

- Lösenordet sparas aldrig. Det används bara under `batteri login`.
- Efter inloggningen sparas en session i `~/.config/batteri/`, läsbar bara för dig. Den
  som kommer åt de filerna kommer åt ditt iCloud-konto på webben, så behandla mappen som
  en hemlighet. Ta bort den med `rm -rf ~/.config/batteri` för att logga ut.
- `batteri` (utan `login`) kan aldrig starta en inloggning själv. Den återanvänder bara
  den sparade sessionen.
- Inget skickas någon annanstans än till Apple.
- pyicloud är låst till en bestämd version, eftersom biblioteket hanterar inloggningen.

## Begränsningar

- Tjänsten bakom Hitta på webben är inte ett officiellt API. Apple kan ändra den, och då
  slutar `batteri` fungera tills pyicloud hunnit ikapp.
- Konton som kräver fysisk säkerhetsnyckel stöds inte.
- Laddning visas bara för enheter där Hitta rapporterar det, inte för tangentbord och mus.
- Byggt och provat på macOS. Uppgifterna från Hitta är inte beroende av macOS, men det är
  inte provat på andra system, och Bluetooth-delarna finns bara på Mac.
- Projektet har ingen koppling till Apple.

## Utveckling

```
git clone https://github.com/gunnarr/batteri
cd batteri
uv run pytest                  # testerna gör inga nätverksanrop
uv run batteri                 # kör från källkoden
uv tool install --editable .   # installera kommandot från din kopia
```

Koden är uppdelad så att all tolkning av data går att testa utan nätverk:

- `src/batteri/cli.py` – kommandon, inloggning och hämtning från Hitta
- `src/batteri/devices.py` – tolkar Hittas data och bygger tabellen
- `src/batteri/bluetooth.py` – läser Macens Bluetooth-uppgifter
- `src/batteri/settle.py` – väntar in enheter som inte hunnit svara
