# Ändringslogg

## Ej släppt

- `batteri` går direkt vidare till inloggningen när du inte är inloggad, i stället för att
  be dig köra `batteri login`.
- Fel kod vid inloggning ger en ny kod och ett nytt försök.
- För program som anropar `batteri`: slutkod 3 när inloggning behövs, språkneutrala fält i
  `--json` (`device_class`, `source`, `left`, `right`, `case`) och `batteri login --stdio`.

## 2026-11-17

- Första versionen: `batteri` visar batterinivå för alla enheter på Apple-kontot, hämtat
  från Hitta. `batteri login` loggar in med Apple-ID och tvåfaktorskod.
- AirPods fylls i med Macens senast kända Bluetooth-värde.
- Anslutna tillbehör som tangentbord och mus visas med aktuell nivå.
- Enheter som oväntat står som offline väntas in i upp till cirka åtta sekunder innan
  listan visas. Enheter som var offline redan förra gången väntas inte in.
- Ny README med installationsanvisning. Fungerar nu från Python 3.11.
- Tester på varje PR, Dependabot och `@claude`-workflow.
