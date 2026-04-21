# Use Cases & Examples — bag-health-mcp

Real-world queries by audience. Indicate per example ob ein API-Schlüssel erforderlich ist.

Alle Tools dieses Servers benötigen **keinen API-Schlüssel** (öffentliche Daten des BAG).

### 🏫 Bildung & Schule
Lehrpersonen, Schulbehörden, Fachreferent:innen

**Lagebeurteilung für den eigenen Kanton**
«Wie ist die aktuelle Situation bezüglich Grippe und Keuchhusten (Pertussis) im Kanton Zürich?»
→ `bag_get_canton_situation(canton="ZH")`
Warum nützlich: Erlaubt Schulbehörden einen schnellen, wöchentlichen Überblick über zirkulierende Krankheiten, um gegebenenfalls Präventionsmassnahmen oder Informationsschreiben an Eltern vorzubereiten.

**Masernfälle in der Region überprüfen**
«Gab es in diesem Jahr bereits gemeldete Masernfälle im Kanton Bern?»
→ `bag_get_disease_data(series_id="measles/cases/incValue/year", canton="BE")`
Warum nützlich: Masern sind hochansteckend; ein einziger Fall kann bei tiefer Durchimpfungsrate an einer Schule einen Ausbruch bedeuten. Die Schulleitung kann so proaktiv das Risiko abschätzen.

### 👨👩👧 Eltern & Schulgemeinde
Elternräte, interessierte Erziehungsberechtigte

**Verständnis von Abwasser-Daten**
«Was zeigen die aktuellen Abwasserdaten zum Coronavirus in der Schweiz?»
→ `bag_get_disease_data(series_id="wastewater_viral_load/NA/value/date", canton="all")`
Warum nützlich: Eltern können sich ein Bild der tatsächlichen Virenzirkulation machen, unabhängig von der Anzahl durchgeführter Tests, um besonders gefährdete Familienmitglieder besser zu schützen.

**Informationen zu Zeckenerkrankungen**
«Wie hoch ist die aktuelle Inzidenz von Lyme-Borreliose im Vergleich zu den letzten Wochen?»
→ `bag_get_disease_data(series_id="lyme_borreliosis/cases/incValue/iso_week", canton="all")`
Warum nützlich: Hilft Eltern, nach Schulausflügen in den Wald das Risiko für zeckenübertragene Krankheiten einzuordnen und entsprechende Vorsicht walten zu lassen.

### 🗳️ Bevölkerung & öffentliches Interesse
Allgemeine Öffentlichkeit, politisch und gesellschaftlich Interessierte

**Überblick über sexuell übertragbare Infektionen (STI)**
«Nehmen die Fälle von Syphilis und Gonorrhoe in der Schweiz tendenziell zu?»
→ `bag_list_series(topic="syphilis")`
→ `bag_get_disease_data(series_id="syphilis/cases/incValue/year", canton="all")`
Warum nützlich: Schafft Transparenz für die Zivilgesellschaft über langfristige epidemiologische Entwicklungen und unterstützt die sachliche Diskussion über Präventionskampagnen.

**Datenverfügbarkeit prüfen**
«Welche Infektionskrankheiten werden vom BAG überhaupt überwacht?»
→ `bag_list_diseases()`
Warum nützlich: Fördert das Verständnis für die Arbeit der Gesundheitsbehörden und zeigt der Bevölkerung, welche Gesundheitsdaten öffentlich und transparent als Open Data zur Verfügung stehen.

### 🤖 KI-Interessierte & Entwickler:innen
MCP-Enthusiast:innen, Forscher:innen, Prompt Engineers, öffentliche Verwaltung

**Automatisierter wöchentlicher Gesundheitsbericht**
«Lade den aktuellsten Datensatz zu COVID-19-Abwasserüberwachung als CSV herunter.»
→ `bag_list_export_files(version="latest")`
→ `bag_download_export(file="COVID19_wastewater_viral_load", format="csv")`
Warum nützlich: Ermöglicht Entwickler:innen den Bau automatisierter Dashboards oder Alerting-Systeme, die wöchentlich die neuesten Rohdaten verarbeiten.

**Portfolio-Kombination: Krankheit & Medikamente**
«Welche Medikamente werden von der Grundversicherung übernommen, um die Krankheiten zu behandeln, die im Kanton Genf aktuell am stärksten ansteigen?»
→ `bag_get_canton_situation(canton="GE")`
→ `bag_epl_search(query="Tamiflu")` *(via [bag-epl-mcp](https://github.com/malkreide/bag-epl-mcp))*
Warum nützlich: Zeigt die Stärke der Portfolio-Synergie: Epidemiologische Überwachungsdaten werden direkt mit administrativen Gesundheitsdaten (Medikamentenliste) verknüpft, was komplexe Public-Health-Analysen ermöglicht.

### 🔧 Technische Referenz: Tool-Auswahl nach Anwendungsfall

| Ich möchte… | Tool(s) | Auth nötig? |
|-------------|---------|-------------|
| **Krankheitsthemen entdecken** (z. B. Grippe, Masern) | `bag_list_diseases` | Nein |
| **Datenserien zu einem Thema finden** | `bag_list_series` | Nein |
| **Filter (Alter, Kanton) einer Serie prüfen** | `bag_get_series_details` | Nein |
| **Fallzahlen & Inzidenzen als Zeitreihe abrufen** | `bag_get_disease_data` | Nein |
| **Schnellen Lagebericht für einen Kanton erhalten** | `bag_get_canton_situation` | Nein |
| **Komplette Rohdaten (CSV/JSON) herunterladen** | `bag_list_export_files`, `bag_download_export` | Nein |
| **Prüfen, von wann die Daten stammen** | `bag_get_data_version` | Nein |
