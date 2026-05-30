## Finding: SEC-018 — Input-Validation an Tool-Boundaries (Pydantic strict / Zod)

| Feld | Wert |
|---|---|
| **Severity** | high |
| **Status** | open |
| **Server** | `bag-health-mcp` |
| **Check-Reference** | `SEC-018` |
| **PDF-Reference** | Sec 3 / Sec 4 (Defense-in-Depth) |
| **Verifikations-Status** | `partial` (fail-or-partial policy) |
| **Audit-Datum** | 2026-05-30 |
| **Auditor** | mcp-audit Skill (automatisiert, Claude) |

### Observed Behavior

Der Check wurde mit Status **partial** bewertet.

- Most tools use Pydantic BaseModel input models with constraints: DiseaseDataInput.limit_weeks ge=1,le=600 (server.py:137-143); Literal enums for canton/sex/format/version (server.py:83-88,124-131)

### Expected Behavior

Erfüllung der Pass-Criteria von `SEC-018` (Input-Validation an Tool-Boundaries (Pydantic strict / Zod)). Folgendes fehlt / ist unvollständig:

1. bag_get_canton_situation takes raw 'canton: str="ZH"' and 'include_wastewater: bool' (server.py:593-596) — no Field constraints, only manual list check (server.py:601)
2. NO model_config strict=True / extra='forbid' on ANY input model — Pydantic coercion active, unknown fields silently accepted
3. String fields topic/series_id/file have no min/max_length or pattern; age_group free-form str
4. No tests for invalid-input rejection (out-of-range, extra fields)

### Evidence

- Most tools use Pydantic BaseModel input models with constraints: DiseaseDataInput.limit_weeks ge=1,le=600 (server.py:137-143); Literal enums for canton/sex/format/version (server.py:83-88,124-131)

### Risk Description

Signifikantes Risiko bzw. architektureller Mangel; im laufenden/nächsten Sprint zu beheben.

### Remediation

Folgende Lücken schliessen (Reihenfolge = Priorität):

1. bag_get_canton_situation takes raw 'canton: str="ZH"' and 'include_wastewater: bool' (server.py:593-596) — no Field constraints, only manual list check (server.py:601)
2. NO model_config strict=True / extra='forbid' on ANY input model — Pydantic coercion active, unknown fields silently accepted
3. String fields topic/series_id/file have no min/max_length or pattern; age_group free-form str
4. No tests for invalid-input rejection (out-of-range, extra fields)

Detail-Schritte und Code-Pattern siehe `checks/SEC-018.md` im Skill-Repo (Remediation-Sektion).

### Effort Estimate

**M** — (S: <1d · M: 1–3d · L: 1–2w · XL: >2w)

### Verification After Fix

- Re-Audit von `SEC-018` (erneuter mcp-audit-Lauf, catalog_hash unverändert)
- Status muss auf `pass` wechseln (alle Pass-Criteria erfüllt, keine offenen `gaps` >= Check-Severity)
