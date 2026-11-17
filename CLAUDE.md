# batteri

Kommandoradsverktyg som visar batteristatus för alla enheter på Apple-kontot. Körs lokalt
på Macen, ingen server och ingen deploy.

## Kommandon

```
uv run pytest                  # tester (pytest, inga nätverksanrop)
uv run batteri                 # kör från källkoden
uv tool install --editable .   # installerar kommandot batteri i ~/.local/bin
```

## Arkitektur

- `src/batteri/cli.py` – argument, inloggning (`batteri login`) och hämtning från Hitta via
  pyicloud. All nätverkskod ligger här.
- `src/batteri/devices.py` – ren logik: tolkar Hittas rådata till `Device`, sorterar och
  bygger tabellen. Inga sidoeffekter.
- `src/batteri/bluetooth.py` – läser Macens egna uppgifter (`system_profiler`, `ioreg`):
  senast kända nivå för AirPods och aktuell nivå för anslutna tillbehör. Tolkningen är
  skild från själva kommandoanropen så att den går att testa.

## Konventioner

- Utskrifter och kommentarer på svenska, kod och namn på engelska.
- `batteri` (visning) får aldrig starta en inloggning: den skapar tjänsten med
  `authenticate=False` och utan lösenord, så den kan bara återanvända sparad session.
- Lösenordet sparas aldrig. Apple-ID och session ligger i `~/.config/batteri`, utanför repot.
- pyicloud är låst till en exakt version eftersom biblioteket hanterar Apple-lösenordet.
  Höj den medvetet, inte automatiskt.
- Nya datakällor läggs som rena tolkningsfunktioner med tester på exempeldata.

## Känt

- Hitta lämnar inte ut batterinivå för AirPods. Att lyssna på AirPods Bluetooth-signaler
  provades 2026-11-17 och förkastades: signalen går inte att knyta till en viss ägare.
