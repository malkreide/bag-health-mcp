# CLAUDE.md

## Teil 1 — Portfolio-Konventionen

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

## Teil 2 — Dieses Repo

**ruff: eine Quelle.** Der Pin `0.16.1` steht in `pyproject.toml` — und
**nicht** mehr als eigener Install-Schritt in der CI.

Der CI-Schritt lief nach dem Install der Abhängigkeiten und überschrieb sie.
Eine Abweichung im Pin konnte deshalb in der CI gar nicht auffallen, sondern
nur lokal — wo niemand sie erwartet. Ein manuelles Nachinstallieren von ruff
vor den Gates ist damit nicht mehr nötig und wäre schädlich: Es würde eine
spätere Anhebung hier stillschweigend überstimmen.

Vor dem Lauf `ruff --version` prüfen: ein älteres ruff früher im `PATH`
schlägt den Pin, ohne dass der Install etwas meldet.

### Gate-Befehle (wörtlich aus ci.yml, Python 3.11/3.12/3.13)

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -m "not live"
python -m ruff check src/ tests/ scripts/
python -m ruff format --check src/ tests/ scripts/
python scripts/tool_hashes.py --check      # SEC-022 rug-pull guard
python scripts/check_version_sync.py       # pyproject ↔ server.json / README / src
```

Alle sechs laufen in einem Job auf allen drei Versionen — keine
`if:`-Ausnahme, kein zweiter lint-Job. Ein grünes 3.13 heisst hier also
wirklich, dass alles auf 3.13 lief; im Portfolio ist das nicht durchgehend so.
Ein `fail-fast: false` steht **nicht** da: Eine rote 3.11 bricht 3.12 und 3.13
ab, bevor sie etwas sagen.

Separater Job `secret-scan`: gitleaks 8.21.2, `detect --source . --redact
--verbose --exit-code 1`, mit `fetch-depth: 0`. Lokal stellt ihn keiner der
Befehle oben nach — ein roter PR bei grünen Tests ist meistens er.

### Live-Tests

`.github/workflows/live.yml` fährt sie täglich (cron `17 6 * * *`, dazu
`workflow_dispatch`): `PYTHONPATH=src pytest tests/ -m live --timeout=30`.
Rot öffnet ein Issue mit Label `live-failure`, der nächste grüne Lauf
schliesst es wieder. Kein Retry — er verdeckte genau den Fall, für den der
Lauf da ist.

Zwei Dinge, die stillschweigend zurück nach DRIFT-005 führen: GitHub
deaktiviert Scheduled Workflows nach 60 Tagen ohne Repo-Aktivität, und ein
`live`-Test, der ohne Quelle grün werden kann, zählt nicht.
