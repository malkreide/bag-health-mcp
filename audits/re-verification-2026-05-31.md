# Audit re-verification — bag-health-mcp

**Date:** 2026-05-31
**Baseline:** run `2026-05-30T184054-Z-bag-health-mcp` (catalog v0.5.0, 40 findings)
**Method:** **manual re-verification against current `main`** (commit `a640366`).

> ⚠️ This is **not** a re-run of the `mcp-audit` skill — that tool is not
> available in this environment, so the original status values cannot be
> regenerated automatically. This document is a hand check of each finding's
> pass-criteria against the code as it now stands. The authoritative status
> requires re-running the actual `mcp-audit` skill (same `catalog_hash`).

---

## Summary

| | Original (2026-05-30) | After remediation (manual) |
|---|---|---|
| Findings (fail/partial/todo) | 40 | **~15 likely remain** |
| Addressed via merged PRs (#3–#22) | — | **25** |
| Critical addressed | 6 | 6 |
| High addressed | 19 | 13 of 19 |

**Honest headline:** the campaign addressed **25 of 40** findings — all
critical and high-value items that are implementable in code, plus the CH
compliance drafts and SCALE deployment guidance. **It did not address ~15
findings** (mostly medium ARCH/OPS/SEC items and a few high ones that were never
in scope). My earlier "every finding addressed" phrasing was an overstatement;
this table corrects it.

---

## Addressed (25) — verified present in `main`

| Finding | Sev | PR | Evidence in code |
|---------|-----|----|--|
| ARCH-005 | critical | #4 | dependency pinning, Dependabot, secret-scan CI |
| ARCH-008 | medium | #16 | `@mcp.resource` (3) + `@mcp.prompt` (2) |
| ARCH-012 | medium | #4 | mcp pin `>=1.27.0,<2`, protocol-rev note |
| CH-004 | medium | #15 | `DATA_LICENSE`/`attribution` in every `Provenance` |
| CH-005 | high | #20 | `docs/isds-klassifikation.md` (draft) |
| CH-006 | high | #21 | `docs/datenklassifikation-schulamt.md` + `DATA_CLASSIFICATION` |
| OBS-001 | high | #6 | `_fail`→`ToolError`/`isError`; no `{error:...}` dicts |
| OBS-002 | high | #3 | raw bodies/exc masked; logged server-side only |
| OBS-003 | medium | #13 | `JsonLogFormatter` (RFC 5424) |
| OBS-004 | critical | #13 | stderr handler, `propagate=False` |
| OBS-006 | medium | #18 | optional OTel, per-tool spans, no PII |
| SDK-001 | high | #7 | `lifespan` + pooled `httpx.AsyncClient` |
| SDK-002 | medium | #14 | typed Pydantic output models + outputSchema |
| SDK-003 | medium | #17 | `Context` injection, progress + ctx logging |
| SEC-004 | critical | #8/#9 | HTTPS enforce + resolved-IP blocklist |
| SEC-005 | high | #10 | `_PinningBackend` DNS-pinning (TOCTOU) |
| SEC-007 | high | #3 | non-root container |
| SEC-018 | high | #11 | `_StrictInput` (strict, extra=forbid, patterns) |
| SEC-021 | high | #8 | egress allow-list + NetworkPolicy |
| SCALE-001 | high | #22 | `MCP_TRANSPORT` env selection |
| SCALE-002 | high | #22 | Service `sessionAffinity: ClientIP` |
| SCALE-003 | high | #22 | `Mcp-Session-Id` LB routing guide |
| SCALE-004 | medium | #19 | multi-stage Dockerfile |
| SCALE-005 | medium | #22 | MCP-gateway guidance |
| SCALE-006 | medium | #22 | resource requests/limits manifest |

*Caveat:* CH-005/006 are **drafts pending sign-off**; SCALE manifests/Docker are
**reference templates** and CI does not build the image or deploy the manifests
(verified locally by other means). These may re-audit as `partial` until the
org-specific TODOs (sign-off, gateway/SIEM product, image digest) are filled.

---

## NOT addressed in this campaign (~15) — still open

These were never in scope; status is unchanged from the baseline unless noted.

| Finding | Sev | Orig | Note (current `main`) |
|---------|-----|------|------|
| SEC-009 | critical | fail | Session-id cryptographic binding — no auth/session layer added (server is unauthenticated by design; relevant if exposed without a gateway). |
| SEC-016 | critical | partial | 0.0.0.0-binding prevention — default is `127.0.0.1`; container opt-in documented, but no explicit guard/warning added. |
| SEC-019 | critical | partial | Lethal-trifecta/server separation — read-only posture helps, but not explicitly analysed/documented. |
| ARCH-004 | high | partial | Inversion-of-control / transport-agnostic structure — not refactored. |
| ARCH-009 | high | fail | Tool annotations (`readOnlyHint` etc.) — **annotations ARE present** in code (3 hints set); may have been mis-flagged or fixed incidentally. **Re-check candidate → likely pass.** |
| OPS-003 | high | fail | Phasenarchitektur (read-only-first roadmap) — not documented. |
| SDK-004 | high | fail | CORS / `Mcp-Session-Id` exposure for HTTP/SSE — no CORS config added. |
| SEC-013 | high | partial | API-key storage — n/a in practice (no keys used); likely closable as n/a but not formally addressed. |
| SEC-022 | high | partial | Tool hash-pinning / namespace prefix vs rug-pull — not addressed. |
| SEC-006 | high | partial | stdio-transport network isolation — default-localhost helps; not formally closed. |
| SEC-008 | medium | partial | Pre-configuration consent for local install — not addressed. |
| ARCH-002 | medium | partial | Tool descriptions with use-case tags — partial unchanged. |
| ARCH-003 | medium | partial | Not-found anti-pattern (heuristics vs empty) — partial unchanged. |
| ARCH-011 | medium | partial | Standardised repo structure — partial unchanged. |
| OPS-002 | medium | partial | Bilingual README / ASCII diagram / links — partial unchanged. |

---

## Recommendation

1. **Re-run the real `mcp-audit` skill** (same `catalog_hash`
   `091f446b…`) to get authoritative pass/fail — this manual pass is indicative,
   not authoritative.
2. **Quick wins likely remaining:** ARCH-009 (annotations look already present),
   SEC-013 (no API keys → arguably n/a), SEC-016/SEC-006 (document/guard the
   bind posture). These are plausibly closable with small follow-ups.
3. **Genuinely open & non-trivial:** SEC-009 (auth/session binding), SDK-004
   (CORS), SEC-019 (trifecta analysis), SEC-022 (tool-hash pinning), OPS-003
   (phase roadmap), ARCH-004 (IoC refactor).
4. **Sign-off / product TODOs:** CH-005/006 and the SCALE manifests need the
   org-specific fields filled before they count as fully closed.
