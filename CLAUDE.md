# CLAUDE.md

## Teil 1 — Portfolio-Konventionen

### Vor der Arbeit

Klon-Aktualität prüfen: `git fetch origin main && git rev-list --count HEAD..origin/main`
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

### ruff-Version

`ruff==0.16.1`, an zwei Stellen exakt gleich gepinnt:
`.github/workflows/ci.yml` und `pyproject.toml` `[dev]`. `pip install -e
".[dev]"` liefert damit dieselbe Version, die die CI fährt. Beide Pins nur
zusammen hochziehen.

Eine `.pre-commit-config.yaml` existiert in diesem Repo **nicht** — es gibt
keine Hooks, die Gates laufen von Hand oder in der CI.

### Gate-Befehle (wörtlich aus ci.yml, Python 3.11/3.12/3.13)

```bash
pip install -e ".[dev]"
PYTHONPATH=src pytest tests/ -m "not live"
pip install ruff==0.16.1
python -m ruff check src/ tests/ scripts/
python -m ruff format --check src/ tests/ scripts/
python scripts/tool_hashes.py --check      # SEC-022 rug-pull guard
python scripts/check_version_sync.py       # pyproject ↔ server.json / README / src
```

Separater Job `secret-scan`: gitleaks 8.21.2, `detect --source . --redact
--verbose --exit-code 1`, mit `fetch-depth: 0`.

### Live-Tests

`.github/workflows/live.yml` fährt sie täglich (cron `17 6 * * *`, dazu
`workflow_dispatch`): `PYTHONPATH=src pytest tests/ -m live --timeout=30`.
Rot öffnet ein Issue mit Label `live-failure`, der nächste grüne Lauf
schliesst es wieder. Kein Retry — er verdeckte genau den Fall, für den der
Lauf da ist.

Zwei Dinge, die stillschweigend zurück nach DRIFT-005 führen: GitHub
deaktiviert Scheduled Workflows nach 60 Tagen ohne Repo-Aktivität, und ein
`live`-Test, der ohne Quelle grün werden kann, zählt nicht.
