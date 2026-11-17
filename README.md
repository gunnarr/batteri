# batteri

Visar batteristatus för alla enheter på ditt Apple-konto i terminalen – samma uppgifter
som appen Hitta har, men med procent och utan att öppna någon app.

```
batteri login     # en gång, och igen när sessionen gått ut (ungefär varannan månad)
batteri           # visa batteristatus
batteri --familj  # ta med familjemedlemmars enheter
batteri --json    # maskinläsbart
```

## Hur det fungerar

Hittas lokala cache på Macen (`~/Library/Caches/com.apple.findmy.fmipcore`) är krypterad,
så uppgifterna hämtas i stället från samma tjänst som icloud.com/find använder, via
biblioteket [pyicloud](https://github.com/timlaing/pyicloud).

- `batteri login` frågar efter Apple-ID, lösenord och en tvåfaktorskod. Lösenordet sparas
  inte. Med `--op op://valv/objekt/password` läses det direkt från 1Password.
- Sessionen sparas i `~/.config/batteri/session` (bara läsbar för dig).
- `batteri` återanvänder bara den sparade sessionen och kan aldrig själv starta en ny
  inloggning.

Utöver Hitta läser `batteri` Macens egna Bluetooth-uppgifter: senast kända nivå för AirPods
(som Hitta inte lämnar ut) och aktuell nivå för anslutna tillbehör som tangentbord och mus.

API:t är inofficiellt och kan sluta fungera om Apple ändrar något. pyicloud är låst till en
bestämd version i `uv.lock`.

## Utveckling

```
uv run pytest
uv tool install --editable .   # installerar kommandot batteri
```
