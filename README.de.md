# 🏥 bag-health-mcp

[![PyPI](https://img.shields.io/pypi/v/bag-health-mcp)](https://pypi.org/project/bag-health-mcp/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Swiss Public Data MCP Portfolio](https://img.shields.io/badge/Portfolio-Swiss%20Public%20Data%20MCP-red)](https://github.com/malkreide)

> Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide) — KI-Modelle mit Schweizer Öffentlichen Daten verbinden.

**[🇬🇧 English version](README.md)**

MCP-Server für das **Infektionskrankheiten-Dashboard (IDD)** des Bundesamts für Gesundheit (BAG). Zugriff auf epidemiologische Überwachungsdaten für 51 Krankheitserreger — darunter Grippe, COVID-19, Masern, Abwasser-Surveillance und mehr.

---

## 🎯 Ankerquery

```
"Wie ist die aktuelle Grippesituation im Kanton Zürich?"
→ bag_health_mcp__get_canton_situation(canton="ZH")

"Wie hat sich der Alkoholkonsum bei 15-Jährigen im Kanton Zürich seit 2010
 entwickelt, und wie steht der Kanton im Schweizer Vergleich da?"
→ bag_health_mcp__search_health_indicators(source="suchtschweiz", topic="alkohol")
→ bag_health_mcp__get_indicator_series(source="suchtschweiz",
      indicator_id="monam/alkoholkonsum-alter-11-15", region="ZH", year_from=2010)
→ Weitere Anwendungsbeispiele nach Zielgruppe →
```

> **Hinweis zur Ankerquery:** Die HBSC-Jugendreihe (über Obsan) beantwortet den
> **gesamtschweizerischen** Verlauf seit 2010 (mit 95%-Konfidenzintervallen). Sie
> ist **national, nicht kantonal** — die Antwort enthält daher eine `region_note`,
> die erklärt, dass ein «Kanton ZH vs. Schweiz»-Vergleich auf dieser Befragung
> nicht möglich ist (HBSC ist nicht kantonal repräsentativ). Es handelt sich um
> **aggregierte Bevölkerungsstatistik — keine individuelle Beratung.**

---

## 🏫 Relevanz für Schulen & Stadtverwaltung

**Schulamt / Kreisschulbehörden:**
- Grippe- und ARI-Inzidenz im eigenen Kanton überwachen
- Masernfall → Alarmierung von Schulen mit tiefer Impfquote
- Pertussis-Monitoring → Schutz von ungeimpften Säuglingen (Geschwister von Schulkindern)

**Stadtverwaltung / KI-Fachgruppe:**
- Wöchentliches Public Health Reporting mit strukturierten Daten
- Abwasser-Surveillance als Frühindikator (~1 Woche vor klinischen Fällen)

**Synergie im Portfolio:**
- `bag-epl-mcp` → «Was wird erstattet?» (Medikamentenliste)
- `bag-health-mcp` → «Was grassiert gerade?» (Surveillance)

---

## 🔧 Verfügbare Tools

| Tool | Beschreibung |
|------|-------------|
| `bag_health_mcp__list_diseases` | Alle 51 Krankheitsthemen auflisten |
| `bag_health_mcp__list_series` | Datenserien für ein Thema anzeigen |
| `bag_health_mcp__get_series_details` | Verfügbare Filter (Kanton, Alter, Geschlecht) |
| `bag_health_mcp__get_disease_data` | Zeitreihen-Daten abrufen |
| `bag_health_mcp__get_canton_situation` | Lageübersicht für einen Kanton |
| `bag_health_mcp__list_export_files` | Exportdateien auflisten |
| `bag_health_mcp__download_export` | CSV/JSON-Export herunterladen |
| `bag_health_mcp__get_data_version` | Aktueller Datenstand (jeweils Mittwoch) |

**Gesundheitsindikatoren — Obsan, Versorgungsatlas & Sucht Schweiz:**

| Tool | Beschreibung |
|------|-------------|
| `bag_health_mcp__search_health_indicators` | Indikatoren suchen nach `source` (`obsan` / `versorgungsatlas` / `suchtschweiz`), Thema, Region, Jahresbereich |
| `bag_health_mcp__get_indicator_series` | Nationale Zeitreihe eines Indikators (mit 95%-CI, wo vorhanden) |

> ⚠️ **Nur aggregierte Bevölkerungsstatistik** (Prävalenzen/Kennzahlen nach
> Alter/Geschlecht/Region) — **keine individuelle Beratung, Diagnose oder
> Fallbeurteilung, kein Personenbezug.** Dies steht in beiden Tool-Beschreibungen
> und in jeder Antwort (`aggregate_statistics_notice`) und ist besonders für
> `suchtschweiz` (HBSC) relevant, da diese Daten Präventionsthemen im Schulkontext
> berühren. Quellen: Obsan (`ind.obsan.admin.ch`, JSON-API); Sucht Schweiz HBSC
> über den Obsan-Spiegel; Versorgungsatlas liefert Indikator-Metadaten + Dimensionen
> (numerische Werte nur im interaktiven Atlas). Siehe `docs/tool-design-health-indicators.md`.

---

## 📡 Datenquelle

- **IDD API**: `https://api.idd.bag.admin.ch` — kein API-Schlüssel erforderlich
- **Aktualisierung**: Jeden Mittwoch
- **Abdeckung**: Schweiz + Liechtenstein, 26 Kantone
- **Themen**: 51 Erreger, 1386 Datenserien

---

## 🚀 Installation

### Claude Desktop (stdio)

```json
{
  "mcpServers": {
    "bag-health": {
      "command": "uvx",
      "args": ["bag-health-mcp"]
    }
  }
}
```

---

## 🖼️ Demo

![Demo: Claude fragt BAG IDD über bag-health-mcp](assets/demo.svg)

*Claude fragt nach der Grippesituation im Kanton Zürich — ein Tool-Call, strukturiertes Ergebnis, handlungsorientierte Zusammenfassung.*

---

## 🔒 Safety & Limits

| Aspekt | Details |
|--------|---------|
| Zugriff | Nur lesend — keine Schreiboperationen möglich |
| Personendaten | Keine — BAG-IDD-Daten sind gesetzlich auf Kantonsebene aggregiert und anonymisiert |
| Rate Limits | Keine publizierten IDD-API-Limits; Server begrenzt Antworten auf 104 Datenpunkte pro Abfrage (`limit_weeks`-Parameter) |
| Timeout | 30 Sekunden pro API-Aufruf |
| Authentifizierung | Kein API-Key erforderlich — alle Daten öffentlich zugänglich |
| Datenlizenz | opendata.swiss OGD — **freie Nutzung mit Quellenangabe** (CC-BY-äquivalent), **nicht** gemeinfrei. Quelle BAG IDD ist zu nennen |
| Nutzungsbedingungen | Es gelten die [ToS der BAG IDD API](https://api.idd.bag.admin.ch) |

---

## ⚠️ Bekannte Einschränkungen

- **Beta-API**: Das IDD-API ist als `v0.1 beta` gekennzeichnet — Schema kann sich ohne Vorankündigung ändern
- **Wöchentlicher Rhythmus**: Keine Echtzeit-Daten; Aktualisierung jeweils mittwochs
- **Kantonsebene**: Bei seltenen Krankheiten werden Daten aus Datenschutzgründen unterdrückt
- **Altersgruppen**: Verfügbare Dimensionen variieren je nach Datenserie — `bag_health_mcp__get_series_details` verwenden

## 🧭 Phasenarchitektur & Compliance

Dieser Server ist ein **Phase-1-Server (nur lesend)**; schreibende/sendende
Funktionen sind bewusst zurückgestellt (Vermeidung der «Lethal Trifecta»). Vor
einer künftigen Schreib-Phase gelten dokumentierte Voraussetzungen
(Server-Trennung, AuthN/Z, Neueinstufung, Audit-Trail) — siehe
[`docs/roadmap.md`](docs/roadmap.md).

- **Sicherheits-Posture** (Lethal-Trifecta-Bewertung, Secret-Management,
  Netzwerk-Exposition): [`docs/security-posture.md`](docs/security-posture.md)
- **ISDS-Schutzbedarf / Datenklassifikation Schulamt**:
  [`docs/isds-klassifikation.md`](docs/isds-klassifikation.md),
  [`docs/datenklassifikation-schulamt.md`](docs/datenklassifikation-schulamt.md)
- **Schwachstellen melden**: siehe die [Sicherheitsrichtlinie](SECURITY.de.md), wie
  Sicherheitsprobleme vertraulich gemeldet werden.
