# ISDS-Schutzbedarfsklassifikation — bag-health-mcp

**Rahmen:** Informationssicherheit und Datenschutz (ISDS), ISDS-Richtlinie der
Stadt Zürich / OIZ.
**Objekt:** `bag-health-mcp` — MCP-Server für das BAG Infectious Disease
Dashboard (IDD).
**Status: ENTWURF — noch nicht durch ISBO/OIZ freigegeben** (siehe
[Freigabe](#7-freigabe-sign-off)).
**Version:** 0.1 · **Letzte Aktualisierung:** 2026-05-31

> ⚠️ Dieses Dokument ist ein technisch begründeter Entwurf der
> Schutzbedarfsanalyse, erstellt aus den tatsächlichen Eigenschaften des
> Systems. Die **verbindliche Einstufung und Freigabe** obliegt der/dem
> ISDS-Beauftragten (ISBO) bzw. OIZ und ist in Abschnitt 7 offen. Die mit
> `TODO` markierten Felder erfordern organisatorische Entscheide.

---

## 1. Systembeschreibung

| Feld | Wert |
|------|------|
| Anwendung | `bag-health-mcp` (MCP-Server, read-only) |
| Zweck | Zugriff auf öffentliche epidemiologische Überwachungsdaten des BAG (IDD) als Entscheidungsunterstützung (u. a. Schulamt / Public-Health-Reporting) |
| Datenquelle | BAG IDD API (`https://api.idd.bag.admin.ch`), Open Government Data, opendata.swiss |
| Datenart | Aggregierte, anonymisierte Surveillance-Daten auf Kantonsebene — **keine Personendaten** |
| Datenfluss | Ausschliesslich **ausgehend lesend** zur BAG-IDD-API; keine Schreibvorgänge, keine Persistenz |
| Authentisierung | Keine (öffentliche Daten, kein API-Key) |
| Betrieb | stdio (lokal) oder Streamable-HTTP (Container/Cloud) |

Datenschutzrechtliche Einordnung: Die verarbeiteten Daten enthalten **keine
Personendaten** im Sinne des kantonalen/eidg. Datenschutzrechts (Aggregation und
Anonymisierung auf Kantonsebene erfolgen gesetzlich durch das BAG). Eine
Bearbeitung besonders schützenswerter Personendaten findet **nicht** statt.

---

## 2. Schutzbedarfsanalyse je Grundwert

Bewertet werden die drei Grundwerte **Vertraulichkeit**, **Integrität** und
**Verfügbarkeit** in den Klassen `tief` / `normal` / `hoch` / `sehr hoch`. Die
Begründungen stützen sich auf nachweisbare Systemeigenschaften (umgesetzte
Massnahmen siehe Abschnitt 4).

### 2.1 Vertraulichkeit — **tief**

| Aspekt | Beurteilung |
|--------|-------------|
| Daten | Öffentliche OGD; keine Personendaten, keine besonders schützenswerten Daten. |
| Geheimnisse im System | Keine. Kein API-Key, keine Credentials, kein Secret-Store nötig; CI-Secret-Scanning aktiv (ARCH-005). |
| Begründung | Eine Offenlegung der Daten verursacht **keinen** Schaden — die Daten sind bereits publiziert. Der Schutzbedarf der Vertraulichkeit ist damit `tief`. |

*Hinweis:* Obwohl der Datenschutzbedarf tief ist, werden Betriebsdetails (rohe
Fehlertexte, Upstream-Bodies) bewusst **nicht** an das LLM/den Client geleakt
(OBS-002), um keine internen Informationen offenzulegen.

### 2.2 Integrität — **normal**

| Aspekt | Beurteilung |
|--------|-------------|
| Quelle | Autoritative Bundesquelle (BAG IDD) über TLS; ausschliesslich HTTPS erzwungen. |
| Manipulationsschutz | Egress-Allow-List + Resolved-IP-Blocklist + DNS-Pinning verhindern Umleitung auf gefälschte Endpunkte (SEC-004/005/021). Eingaben werden strikt validiert (SEC-018). |
| Folgen einer Verfälschung | Daten dienen als Entscheidungsgrundlage (z. B. Schulamt). Verfälschte Werte könnten zu falschen Lageeinschätzungen führen — jedoch **keine** unmittelbare Gefahr für Leib/Leben, da advisorisch und wöchentlich aktualisiert. |
| Begründung | Server ist **read-only** und verändert keine Daten; Integrität hängt an der Quelle und am Transport, beide gehärtet. Schutzbedarf `normal`. |

### 2.3 Verfügbarkeit — **normal**

| Aspekt | Beurteilung |
|--------|-------------|
| Kritikalität | Entscheidungsunterstützung, nicht zeitkritisch/echtzeitkritisch; Quelldaten werden nur **wöchentlich** (mittwochs) aktualisiert. |
| Abhängigkeit | Externe Verfügbarkeit der BAG-IDD-API; Ausfälle werden sauber als `isError`-Toolresultate signalisiert (OBS-001), kein Absturz. |
| Folgen eines Ausfalls | Temporär keine Lageabfrage möglich; Rückgriff auf das IDD-Webportal jederzeit möglich. Kein Notfall-/Leitsystem. |
| Begründung | Kurzzeitige Nichtverfügbarkeit ist tolerierbar; kein 7×24-SLA erforderlich. Schutzbedarf `normal`. |

> **TODO (ISBO/Fachstelle):** Bestätigen oder anpassen, falls der konkrete
> Einsatz (z. B. verbindliche Grundlage für Schulschliessungsentscheide) einen
> höheren Verfügbarkeits-/Integritätsbedarf begründet.

---

## 3. Resultierende Schutzbedarfsklasse

| Grundwert | Schutzbedarf (Entwurf) | Massgeblich |
|-----------|------------------------|-------------|
| Vertraulichkeit | **tief** | öffentliche Daten, keine Personendaten/Geheimnisse |
| Integrität | **normal** | read-only, gehärteter Transport, advisorischer Charakter |
| Verfügbarkeit | **normal** | wöchentliche Daten, tolerierbare Ausfälle |

**Gesamteinstufung (Entwurf): normal** (Maximumprinzip über die Grundwerte;
Vertraulichkeit tief, Integrität/Verfügbarkeit normal).

> **TODO (ISBO/OIZ):** Verbindliche Festlegung der Schutzbedarfsklasse gemäss
> ISDS-Richtlinie und Eintrag im Informationssicherheits-Inventar.

---

## 4. Massnahmen-Mapping

Die folgenden technischen Massnahmen sind im Code umgesetzt und decken die je
Grundwert relevanten Schutzziele ab. (Referenzen = Audit-Findings / PRs.)

| Schutzziel | Massnahme | Umgesetzt (Referenz) |
|------------|-----------|----------------------|
| Integrität / SSRF | HTTPS erzwungen, Egress-Allow-List (feste 3-Host-Liste: BAG IDD, Obsan, Versorgungsatlas), auf jedem Redirect-Hop geprüft | SEC-021, SEC-004 |
| Integrität / SSRF | Resolved-IP-Blocklist (private/link-local/Metadata blockiert) | SEC-004 |
| Integrität / SSRF | Ausgehendes DNS-Pinning gegen TOCTOU/Rebinding | SEC-005 |
| Integrität | Strikte Input-Validierung an den Tool-Grenzen (Pydantic strict, Pattern/Längen) | SEC-018 |
| Vertraulichkeit | Kein Leak von Roh-Fehlern/Upstream-Bodies an Client/LLM; Logs nur stderr | OBS-001, OBS-002, OBS-004 |
| Vertraulichkeit / Lieferkette | Keine Hardcoded-Secrets, Secret-Scanning + Dependency-Pinning/Dependabot | ARCH-005/012 |
| Betrieb / Härtung | Non-root-Container (uid 10001), Multi-Stage-Build (keine Build-Tools im Image), HEALTHCHECK | SEC-007, SCALE-004 |
| Betrieb / Netzwerk | Bind standardmässig auf 127.0.0.1; All-Interfaces nur explizit (Container) | SEC-006/016 |
| Betrieb / Netzwerk (Layer 2) | Begleitende Kubernetes-NetworkPolicy (Egress nur DNS+HTTPS) | SEC-021 |
| Nachvollziehbarkeit | Strukturiertes JSON-Logging (RFC 5424) auf stderr; optional OpenTelemetry-Tracing (ohne PII) | OBS-003, OBS-006 |
| Datenherkunft | Provenance + Lizenz/Attribution in jeder Antwort | CH-004, SDK-002 |

Für die Einstufung **normal** sind keine zusätzlichen Massnahmen über den
umgesetzten Stand hinaus zwingend. Bei einer Höherstufung (siehe TODO oben)
wären u. a. zu prüfen: Verfügbarkeits-SLO/Redundanz (SCALE-001/002/003),
Ressourcenlimits pro Container (SCALE-006), zentrales Log-/Trace-Backend.

---

## 5. Restrisiken

- **Externe Abhängigkeit:** Verfügbarkeit/Integrität hängen von der BAG-IDD-API
  ab; diese liegt ausserhalb der Kontrolle der Stadt. Mitigiert durch saubere
  Fehlerbehandlung (kein Absturz, `isError`) und gehärteten Transport.
- **Beta-API:** Das IDD-API ist als `v0.1 beta` deklariert; Schemaänderungen
  möglich (siehe README «Known Limitations»).
- **Fehlinterpretation:** Aggregierte Daten könnten fachlich falsch
  interpretiert werden — organisatorisch (Schulung der Fachpersonen), nicht
  technisch zu adressieren.

---

## 6. Geltungsbereich & Annahmen

- Bewertet wird der Server `bag-health-mcp` in der hier dokumentierten Form
  (read-only, nur BAG-IDD-Zugriff). Eine Ausweitung auf schreibende Tools oder
  weitere Datenquellen erfordert eine **Neubewertung**.
- Annahme: Betrieb erfolgt in einer kontrollierten Umgebung der Stadt/des OIZ
  gemäss den dokumentierten Container-/Netzwerkvorgaben.

---

## 7. Freigabe (Sign-off)

> Diese Einstufung ist erst nach Gegenzeichnung verbindlich.

| Rolle | Name | Datum | Visum |
|-------|------|-------|-------|
| Ersteller (technisch) | _automatisiert erstellter Entwurf_ | 2026-05-31 | — |
| Fachverantwortung / Dateneigner | TODO | TODO | TODO |
| ISDS-Beauftragte/r (ISBO) | TODO | TODO | TODO |
| OIZ / Informationssicherheit | TODO | TODO | TODO |

---

*Begriffe: ISDS = Informationssicherheit und Datenschutz; ISBO =
ISDS-Beauftragte/r; OIZ = Organisation und Informatik Zürich; Grundwerte =
Vertraulichkeit / Integrität / Verfügbarkeit.*
