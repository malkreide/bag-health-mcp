## Finding: OBS-006 — OpenTelemetry Distributed Tracing pro Tool-Call

| Feld | Wert |
|---|---|
| **Severity** | medium |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `OBS-006` |
| **PDF-Reference** | Anhang B10 |
| **Verifikations-Status** | `fail` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **fail** bewertet.

- is_cloud_deployed=true so check applies (HTTP at server.py:741)
- No opentelemetry/otel anywhere — not in src/ or pyproject.toml
- No TracerProvider/OTLP exporter/HTTPXClientInstrumentor/per-tool spans
- No OTEL_* config

### Expected Behavior

Erfüllung der Pass-Criteria von `OBS-006` (OpenTelemetry Distributed Tracing pro Tool-Call). Folgendes fehlt / ist unvollständig:

1. Add OpenTelemetry SDK + OTLP exporter, instrument httpx, wrap each tool in a span (no PII), env-configurable endpoint

### Evidence

- is_cloud_deployed=true so check applies (HTTP at server.py:741)
- No opentelemetry/otel anywhere — not in src/ or pyproject.toml
- No TracerProvider/OTLP exporter/HTTPXClientInstrumentor/per-tool spans
- No OTEL_* config

### Risk Description

Best-Practice-Verletzung ohne akutes Risiko; für den nächsten Sprint einzuplanen.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. Add OpenTelemetry SDK + OTLP exporter, instrument httpx, wrap each tool in a span (no PII), env-configurable endpoint

Detail-Schritte und Code-Pattern siehe `checks/OBS-006.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `OBS-006` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
