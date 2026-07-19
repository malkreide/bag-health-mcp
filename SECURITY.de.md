# Sicherheitsrichtlinie

**[🇬🇧 English version](SECURITY.md)**

Dieser Server ist Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide).

---

## Eine Schwachstelle melden

Bitte melde Sicherheitslücken **vertraulich** — eröffne für Sicherheitsprobleme
kein öffentliches Issue.

- Nutze die [GitHub Security Advisories](https://github.com/malkreide/bag-health-mcp/security/advisories/new)
  (bevorzugt), oder
- kontaktiere die Maintainerin/den Maintainer direkt.

Bitte gib an:
- Eine Beschreibung der Schwachstelle und ihrer Auswirkung
- Schritte zur Reproduktion (nach Möglichkeit ein Proof of Concept)
- Betroffene Version / Commit

Wir bestätigen Meldungen in der Regel innerhalb weniger Tage und stimmen den
Zeitplan für Fix und Veröffentlichung mit dir ab.

---

## Unterstützte Versionen

Dies ist ein Phase-1-Server (nur lesend) in aktiver Entwicklung. Sicherheitsfixes
werden auf die aktuellste veröffentlichte Version auf [PyPI](https://pypi.org/project/bag-health-mcp/)
und den `main`-Branch angewendet. Für den Produktivbetrieb auf eine bestimmte
veröffentlichte Version oder einen Git-Tag festlegen.

---

## Sicherheitsmodell

Der Server folgt einem Design **ausschliesslich öffentlicher Daten, nur lesend**:

- **Keine Authentifizierung / keine Secrets** — er greift nur auf öffentliche
  Schweizer Open-Government-Data-APIs zu (BAG IDD, Obsan, Versorgungsatlas), die
  keinen API-Schlüssel und keine Zugangsdaten erfordern. Sucht-Schweiz/HBSC-Reihen
  werden über den Obsan-Spiegel bezogen.
- **Nur lesende Operationen** — jedes Tool führt ausschliesslich HTTPS-`GET`-
  bzw. `POST`-Abfragen aus; es gibt keine Schreib-, Sende- oder Ausführungsfunktionen.
- **Keine Personendaten** — alle Daten sind an der Quelle aggregiert/anonymisiert:
  BAG IDD auf Kantonsebene mit Unterdrückung kleiner Fallzahlen; die Indikatoren
  sind Bevölkerungs-Aggregate nach Alter/Geschlecht/Region.
- **Egress-Allow-List** — der Server kontaktiert ausschliesslich eine feste Liste
  von drei öffentlichen Datenhosts (`api.idd.bag.admin.ch`, `ind.obsan.admin.ch`,
  `www.versorgungsatlas.ch`), nur über HTTPS, durchgesetzt bei jeder Anfrage
  inklusive Redirect-Hops (SSRF-Schutz), mit einer ergänzenden Richtlinie auf
  Netzwerkebene in [`deploy/networkpolicy.yaml`](deploy/networkpolicy.yaml).
- **Netzwerk-Exposition** — der Standard-Transport stdio hat keine Netzwerkfläche;
  HTTP bindet standardmässig an `127.0.0.1` und bindet alle Interfaces nur nach
  ausdrücklicher Aktivierung (`MCP_HOST=0.0.0.0`) für netzwerkisolierte
  Deployments.

### Lethal-Trifecta-Bewertung

Der Server hält **höchstens eines** der drei Elemente (private Daten, nicht
vertrauenswürdige Inhalte, Exfiltrationsfähigkeit), sodass sich die Kette von
Prompt-Injection zu Exfiltration nicht schliessen kann. Die vollständige
Bewertung, die Entscheidung zum Secret-Management und Hinweise zur
Netzwerk-Exposition stehen in [`docs/security-posture.md`](docs/security-posture.md).

Zur Härtung beim Deployment (Gateway, Ressourcenlimits, `NetworkPolicy`) siehe den
[Deployment- & Scaling-Leitfaden](docs/deployment-scaling.md).
