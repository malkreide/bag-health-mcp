# 🏥 bag-health-mcp

[![PyPI](https://img.shields.io/pypi/v/bag-health-mcp)](https://pypi.org/project/bag-health-mcp/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Swiss Public Data MCP Portfolio](https://img.shields.io/badge/Portfolio-Swiss%20Public%20Data%20MCP-red)](https://github.com/malkreide)

> Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide) — connecting AI models to Swiss public data sources.

MCP server for the Swiss Federal Office of Public Health (BAG) **Infectious Disease Dashboard (IDD)**. Access epidemiological surveillance data for 51 pathogens across Switzerland — including influenza, COVID-19, measles, wastewater surveillance, and more.

---

## 🎯 What You Can Do

```
"Wie ist die aktuelle Grippesituation im Kanton Zürich verglichen mit den letzten Wochen?"
→ bag_get_canton_situation(canton="ZH")

"Gibt es aktuell einen Masernausbruch in der Schweiz?"
→ bag_get_disease_data(series_id="measles/cases/incValue/year", canton="all")

"Wie entwickelt sich das SARS-CoV-2-Signal im Abwasser?"
→ bag_list_series(topic="wastewater_viral_load")
→ bag_get_disease_data(series_id="wastewater_viral_load/NA/value/date", ...)

"Welche Krankheitsdaten stellt das BAG aktuell bereit?"
→ bag_list_diseases()
```

---

## 🔧 Tools

| Tool | Description |
|------|-------------|
| `bag_list_diseases` | List all 51 disease topics, grouped by category |
| `bag_list_series` | List data series for a specific disease |
| `bag_get_series_details` | Get available filter dimensions (canton, age, sex) |
| `bag_get_disease_data` | Fetch time-series surveillance data |
| `bag_get_canton_situation` | Situational overview for a canton (Schulamt use case) |
| `bag_list_export_files` | List available complete export datasets |
| `bag_download_export` | Download raw CSV/JSON export |
| `bag_get_data_version` | Current data version (updated every Wednesday) |

---

## 🏫 Relevance for Schools & City Administration

**Schulamt / Kreisschulbehörden:**
- Monitor influenza and ARI incidence in your canton
- Single measles case → alert for schools with low vaccination coverage
- Pertussis tracking → protect unvaccinated infants (siblings of school children)

**Stadtverwaltung / KI-Fachgruppe:**
- Public Health Reporting with structured weekly data
- Wastewater surveillance as 1-week lead indicator before clinical cases

**Synergy with portfolio:**
- `bag-epl-mcp` → "What treatments are listed?" (EPL medication database)
- `bag-health-mcp` → "What is currently spreading?" (surveillance data)

---

## 📡 Data Source

- **IDD API**: `https://api.idd.bag.admin.ch` — No authentication required
- **Update cycle**: Every Wednesday
- **Coverage**: Switzerland + Liechtenstein (FL), 26 cantons
- **Topics**: 51 pathogens, 1386 data series

```
Architecture:
                    ┌─────────────────┐
  MCP Host          │  bag-health-mcp │
  (Claude, etc.) ──▶│  MCP SDK        │──▶ api.idd.bag.admin.ch
                    │  8 Tools        │    (IDD API, no auth)
                    └─────────────────┘
```

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

### Cloud / HTTP

```bash
pip install bag-health-mcp
python -m bag_health_mcp.server --http --port 8000
```

---

## 🗂️ Available Disease Topics

| Category | Topics |
|----------|--------|
| Respiratory | influenza, covid19, acute_respiratory_infection, respiratory_pathogens |
| Enteric | campylobacteriosis, salmonellosis, ehec, listeriosis, hepatitis_a/e |
| STI & Bloodborne | hiv, aids, syphilis, gonorrhea, hepatitis_b/c, chlamydiosis |
| Vaccine-preventable | measles, pertussis, rubella, tetanus, diphtheria, ipd, meningo |
| Vector-borne | lyme_borreliosis, tick-borne_encephalitis, dengue, malaria, zika |
| Wastewater | wastewater_viral_load, wastewater_sequencing |

---

## ⚠️ Known Limitations

- **Beta API**: IDD API is labelled `v0.1 beta` — schema may change without notice
- **Weekly cadence**: Data is not real-time; updated Wednesdays only
- **Canton granularity**: Some rare diseases have insufficient cases for canton-level data (suppressed for privacy)
- **Age groups**: Available dimensions vary by disease series; use `bag_get_series_details` to check

---

## 📄 License

MIT — Data from BAG IDD is public domain (opendata.swiss).

## 🔗 Related Portfolio Servers

- [`swiss-statistics-mcp`](https://github.com/malkreide/swiss-statistics-mcp) — BFS demographic data
- [`bag-epl-mcp`](https://github.com/malkreide/bag-epl-mcp) — BAG medication reimbursement list
- [`zurich-opendata-mcp`](https://github.com/malkreide/zurich-opendata-mcp) — City of Zurich open data
