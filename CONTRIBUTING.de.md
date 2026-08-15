# Mitwirken bei bag-health-mcp

**[🇬🇧 English version](CONTRIBUTING.md)**

Vielen Dank für dein Interesse, etwas beizutragen! Dieser Server ist Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide).

---

## Fehler melden

Nutze die [GitHub Issues](https://github.com/malkreide/bag-health-mcp/issues), um Fehler zu melden oder Funktionen vorzuschlagen.

Bitte gib an:
- Python-Version und Betriebssystem
- Vollständige Fehlermeldung oder Beschreibung des unerwarteten Verhaltens
- Schritte zur Reproduktion

---

## Pull Requests

1. Repository forken
2. Feature-Branch erstellen: `git checkout -b feat/dein-feature`
3. Änderungen vornehmen und Tests ergänzen
4. Sicherstellen, dass alle Tests bestehen: `PYTHONPATH=src pytest tests/ -m "not live"`
5. Mit [Conventional Commits](https://www.conventionalcommits.org/) committen: `feat: add new tool`
6. Pushen und einen Pull Request gegen `main` öffnen

Die Live-Tests gehen gegen die echten BAG- und Obsan-Endpunkte und sind vom Befehl in Schritt 4 ausgeschlossen. So werden sie gefahren:

```bash
PYTHONPATH=src pytest tests/ -m live --timeout=30
```

`--timeout` stammt aus `pytest-timeout` und wird mit dem `dev`-Extra installiert (`pip install -e ".[dev]"`). Ohne das Plugin bricht pytest mit `unrecognized arguments` ab, und ein hängender Endpunkt blockiert den Lauf. Ein geplanter Workflow (`.github/workflows/live.yml`) fährt sie täglich — denn eine aufgezeichnete Fixture belegt die Form einer Antwort zu ihrem Aufnahmedatum, nicht dass die Quelle heute noch so antwortet.

---

## Code-Stil

- Python 3.11+
- [Ruff](https://github.com/astral-sh/ruff) für Linting und Formatierung
- Type Hints für alle öffentlichen Funktionen erforderlich
- Tests für neue Tools erforderlich (`tests/test_server.py`)
- Den bestehenden MCP-/Pydantic-v2-Mustern in `server.py` folgen

---

## Datenquelle

Dieser Server nutzt die BAG Infectious Disease Dashboard (IDD) API — keine Authentifizierung erforderlich:

| Quelle | Dokumentation |
|--------|--------------|
| BAG IDD API | [api.idd.bag.admin.ch](https://api.idd.bag.admin.ch) |
| Swagger-Docs | [api.idd.bag.admin.ch/swagger-ui/api-doc.html](https://api.idd.bag.admin.ch/swagger-ui/api-doc.html) |

Beim Hinzufügen neuer Tools dem bestehenden Muster folgen: Pydantic-Eingabemodell, mit `@mcp.tool` dekorierte async-Funktion, gemockte und Live-Tests.

---

## Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** täglich um 06:17 UTC, dazu jederzeit von Hand über *Actions → Live API tests → Run
workflow*. Siehe [`.github/workflows/live.yml`](.github/workflows/live.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Label `live-failure` (Titel: «Live-Tests gegen die Quelle sind rot»). Ein zweiter roter Lauf erkennt das offene Issue **am Label**, nicht am Titel, und hängt sich an denselben Thread. Wer das Label von Hand entfernt, bekommt beim nächsten roten Lauf ein zweites Issue. Wird die Suite wieder grün, schliesst sich das Issue selbst.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über api.idd.bag.admin.ch widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

## Lizenz

Mit deinem Beitrag erklärst du dich damit einverstanden, dass deine Beiträge unter der [MIT-Lizenz](LICENSE) lizenziert werden.
