# Datenklassifikation (Schulamt-Schema) — bag-health-mcp

**Rahmen:** Klassifikationsschema der Stadt Zürich für das Schulamt
(BUI / VERTRAULICH / STRENG VERTRAULICH).
**Objekt:** `bag-health-mcp` — MCP-Server für das BAG Infectious Disease
Dashboard (IDD).
**Status: ENTWURF — fachliche Bestätigung durch das Schulamt ausstehend**
(siehe [Freigabe](#6-freigabe)).
**Version:** 0.1 · **Letzte Aktualisierung:** 2026-05-31

> ⚠️ Technisch begründeter Entwurf aus den tatsächlichen Dateneigenschaften.
> Die verbindliche fachliche Zuordnung obliegt dem Schulamt / der
> Klassifizierungsverantwortung. `TODO`-Felder erfordern organisatorische
> Entscheide.

---

## 1. Klassifikationsstufen (Schema)

| Stufe | Bedeutung | Beispiel |
|-------|-----------|----------|
| **BUI** (öffentlich / nur für internen Gebrauch, frei verfügbar) | Offenlegung verursacht keinen Schaden | publizierte, anonymisierte Statistik |
| **VERTRAULICH** | Offenlegung kann Personen/Organisation schädigen | personenbezogene Schülerdaten |
| **STRENG VERTRAULICH** | Offenlegung verursacht schweren Schaden | besonders schützenswerte Personendaten |

---

## 2. Einstufung dieses Systems

**Höchste verarbeitete Stufe (Entwurf): BUI (öffentlich).**

| Kriterium | Befund |
|-----------|--------|
| Datenherkunft | BAG IDD, Open Government Data (opendata.swiss) — bereits **publiziert** |
| Personenbezug | **Keiner.** Daten sind gesetzlich auf **Kantonsebene aggregiert und anonymisiert**; das BAG **unterdrückt kleine Fallzahlen an der Quelle** (Schutz vor Re-Identifikation) |
| Granularität im Server | Gröbste/feinste Ebene ist der **Kanton**; der Server aggregiert nie unterhalb dessen, was die OGD-API liefert (`MIN_AGGREGATION_LEVEL = "canton"`) |
| Schreibvorgänge | Keine (read-only) |
| Folgerung | Es werden **keine** VERTRAULICH- oder STRENG-VERTRAULICH-Daten verarbeitet. Höchste Stufe: **BUI**. |

Im Code ist die Einstufung als `DATA_CLASSIFICATION = "ÖFFENTLICH / BUI"`
hinterlegt und wird im Resultat des aggregierenden Tools
(`bag_get_canton_situation`) transparent ausgewiesen.

---

## 3. Aggregations-/Re-Identifikationsrisiko

Der Audit-Punkt verlangt eine dokumentierte Mindestgruppengrösse auf dem
aggregierenden Tool. Bewertung:

- Der Server **erzeugt keine** eigene Feinaggregation. Er gibt ausschliesslich
  die vom BAG bereits aggregierten und für kleine Zellen unterdrückten Werte
  weiter; die feinste exponierte Geo-Ebene ist der **Kanton**
  (`MIN_AGGREGATION_LEVEL`).
- Eine k-Anonymitäts-/Mindestzellgrössen-Unterdrückung erfolgt damit **an der
  Quelle (BAG)**; eine erneute Unterdrückung im Server wäre wirkungslos bzw.
  würde öffentliche Daten ohne Mehrwert verfälschen.
- Der Server kann folglich **keine** re-identifizierende, feinkörnigere Sicht
  herstellen. Diese Eigenschaft ist als Konstante dokumentiert und im
  Tool-Output (Feld `note`) sichtbar gemacht.

> **TODO (Schulamt):** Falls künftig feinere Geo-Ebenen (z. B. Schulkreis,
> Gemeinde) oder Verknüpfungen mit Schülerdaten vorgesehen werden, ist dieses
> Dokument **neu zu bewerten** — dann würden Mindestgruppengrössen und ggf. eine
> Höherstufung relevant.

---

## 4. Massnahmen-Mapping (Stufe BUI)

| Ziel | Massnahme | Referenz |
|------|-----------|----------|
| Keine Personendaten | read-only, nur kantonsaggregierte OGD; Klassifikation als Konstante + im Output | dieses Dokument, `DATA_CLASSIFICATION` |
| Keine Feinaggregation | `MIN_AGGREGATION_LEVEL="canton"`, im Tool-Output ausgewiesen | CH-006 |
| Kein Leak von Betriebsdetails | Fehler-/Body-Maskierung, Logs nur stderr | OBS-001/002/004 |
| Transport-/SSRF-Härtung | HTTPS-Zwang, Egress-Allow-List, IP-Blocklist, DNS-Pinning | SEC-004/005/021 |
| Herkunft/Lizenz transparent | Provenance + Attribution/Lizenz in jeder Antwort | CH-004, SDK-002 |

Für die Stufe **BUI** sind über den umgesetzten Stand hinaus keine zusätzlichen
Vertraulichkeitsmassnahmen erforderlich.

---

## 5. Restrisiken & Annahmen

- Annahme: Das System wird **nicht** mit personenbezogenen Schul-/Schülerdaten
  verknüpft. Eine solche Verknüpfung läge ausserhalb des hier bewerteten Umfangs
  und erforderte eine Neueinstufung (voraussichtlich VERTRAULICH).
- Fachliche Fehlinterpretation aggregierter Daten ist organisatorisch
  (Schulung) zu adressieren, nicht durch Klassifikation.

---

## 6. Freigabe

| Rolle | Name | Datum | Visum |
|-------|------|-------|-------|
| Ersteller (technisch) | _automatisiert erstellter Entwurf_ | 2026-05-31 | — |
| Klassifizierungsverantwortung Schulamt | TODO | TODO | TODO |
| Datenschutz-/ISDS-Stelle | TODO | TODO | TODO |

---

*Verweise: ISDS-Schutzbedarfsklassifikation siehe
[`docs/isds-klassifikation.md`](isds-klassifikation.md).*
