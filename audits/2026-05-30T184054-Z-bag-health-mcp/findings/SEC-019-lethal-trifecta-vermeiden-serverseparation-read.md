## Finding: SEC-019 — Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send

| Feld | Wert |
|---|---|
| **Severity** | critical |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-019` |
| **PDF-Reference** | Anhang B1 |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- `Read-only/write_capable=false: only GET/query-POST to fetch public data; no send_mail/smtplib/slack/webhook exfiltration sinks`
- httpx.post (server.py:408,659) only target the fixed read API; Public Open Data (README.md:133)

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-019` (Lethal Trifecta vermeiden: Server-Separation Read vs Write/Send). Folgendes fehlt / ist unvollständig:

1. No documented Lethal Trifecta assessment in README/docs (grep trifecta/lethal = none; no docs/ dir)
2. Score effectively safe (<=1 leg) but undocumented, so Pass Criteria not fully met

### Evidence

- `Read-only/write_capable=false: only GET/query-POST to fetch public data; no send_mail/smtplib/slack/webhook exfiltration sinks`
- httpx.post (server.py:408,659) only target the fixed read API; Public Open Data (README.md:133)

### Risk Description

Blockiert die Produktionsfreigabe. Konkretes Sicherheits- bzw. Compliance-Risiko, das vor dem nächsten Release adressiert sein muss.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. No documented Lethal Trifecta assessment in README/docs (grep trifecta/lethal = none; no docs/ dir)
2. Score effectively safe (<=1 leg) but undocumented, so Pass Criteria not fully met

Detail-Schritte und Code-Pattern siehe `checks/SEC-019.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**S** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-019` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
