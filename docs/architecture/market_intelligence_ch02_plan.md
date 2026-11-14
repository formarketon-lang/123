# TLP-MIM-001 — Chapter 02 Plan
Project ID: TLP-MIM-001  
Parent Project: TLP-MASTER-001  
Repository: formarketon-lang/123  
Base: main  
Branch: ch02-advance-decline-plan  
Chapter: 02  
Title: Historical Advance / Decline Analysis  
Status: PLAN DRAFT — IMPLEMENTATION NOT STARTED  
Scope: NSE Cash Equity only  
F&O Scanner: Excluded

---

## 1. Entry Gate

Chapter 01 is accepted with review conditions under checkpoint:

`TLP-CP-2026-11-14-TLP-MIM-001-CH01-ACCEPTED-REVIEW-AWARE`

Chapter 01 evidence confirms:
- Official NSE UDiFF CM Bhavcopy workbook mapping: 14/14 field/tag pairs verified.
- NSE UDiFF downloader, schema hash pinning, archive hash and MII reconciliation are implemented.
- Market Regime and review-aware Market Breadth are integrated.
- TradeLab Pro regression: 614/614 passed.
- Yahoo Adapter tests: 56/56 passed.
- Live membership identity/coverage remains REVIEW at 99.2759%; this is a data-quality condition, not permission to treat incomplete coverage as PASS.

Chapter 02 must build on the accepted Main implementation. Do not use the superseded branch `ch01-step36-nse-udiff-ingestion`.

## 2. Chapter Objective

Build a historical, point-in-time NSE cash-equity Advance / Decline analysis service that can produce:
- Daily advancing, declining and unchanged counts.
- Daily Advance-minus-Decline (A-D) difference.
- Advance / Decline ratio, with explicit zero-denominator handling.
- Cumulative Advance / Decline Line across valid trading sessions.
- Coverage and validation status for every date.
- A review-aware chart and table in Market Intelligence.

The existing daily Market Breadth calculation already counts advances, declines and unchanged stocks for one observation date. Chapter 02 must reuse its validated rules and service interfaces where suitable. Do not create a duplicate daily breadth engine.

## 3. Definitions and Calculation Contract

For each NSE trading date and eligible point-in-time MII EQ universe member:
- Advancing: Current Close > Previous Close.
- Declining: Current Close < Previous Close.
- Unchanged: Current Close = Previous Close.
- Missing/invalid observations: excluded and counted as missing; never counted as unchanged.
- A-D Difference: Advancing - Declining.
- A/D Ratio: Advancing / Declining. If Declining = 0, report an explicit special state (e.g. NO_DECLINERS); never emit infinity or silently cap the value.
- Cumulative A-D Line: prior valid cumulative value + current A-D Difference. The series must disclose dates with REVIEW coverage; do not label a provisional segment verified PASS.

Use official NSE MII membership snapshots aligned to each observation date. A current universe must not be retroactively applied to historical dates. Do not substitute Symbol-only matches where ISIN / Instrument ID evidence is required.

## 4. Data and Safety Rules

1. NSE official cash-equity data is primary.
2. Yahoo is secondary fallback only through the existing approved adapter; preserve source and fallback reason for each observation.
3. Use the accepted UDiFF downloader and existing Bhavcopy service; do not add a second archive downloader.
4. Use same-date MII evidence for point-in-time membership.
5. Preserve fetch timestamps, raw archive hash, source, exchange, trade date and validation status.
6. Missing observations remain missing.
7. Identity exceptions remain excluded until authoritative NSE evidence resolves them.
8. Incomplete universe coverage produces REVIEW, not PASS.
9. Invalid prices, duplicate identities, wrong series, non-NSE instruments and malformed dates block the affected date.
10. No fabricated, forward-filled or silently repaired observations.
11. BSE remains disabled.
12. Sector Mapping Expansion remains OFF.
13. F&O Scanner remains excluded.

## 5. Step Plan

### STEP 01 — Inventory Result (2026-11-14)

<badge>INVENTORY VERIFIED — NO CODE CHANGE</badge>

Inspected the current Main implementation:

- Core daily classification: `core/market_intelligence/breadth.py`
- Validated daily breadth service: `services/market_intelligence/breadth_service.py`
- NSE UDiFF + dated MII orchestration: `services/market_intelligence/bhavcopy_service.py`
- Official UDiFF normalization: `data/providers/nse_udiff_bhavcopy.py`
- Dated Symbol / ISIN / Instrument ID reconciliation: `data/providers/nse_bhavcopy_mii_validation.py`
- UI integration: `ui/market_intelligence.py`
- Existing tests: `tests/test_market_intelligence_bhavcopy_service.py`,
  `tests/test_market_intelligence_breadth_service.py`,
  `tests/test_nse_bhavcopy_mii_validation.py`,
  `tests/test_market_intelligence_navigation.py`

Inventory findings:

1. Daily advancing / declining / unchanged classification already exists; Chapter 02 must reuse it rather than create a second daily classifier.
2. The current production Bhavcopy service is single-observation-date and requires a same-date MII snapshot. Historical A/D therefore needs an explicit per-date orchestration contract.
3. The MII reconciliation already supports Symbol + ISIN and Instrument ID when available on both sources, and excludes mismatches.
4. Existing breadth service preserves source, fallback reason, timezone-aware fetch timestamps and validation status.
5. Historical point-in-time MII availability and the cumulative A-D Line are not implemented by the inspected service. These are Chapter 02 gaps, not assumptions that may be bypassed.
6. No existing Chapter 02 production module was found in the inspected paths. No duplicate downloader or new adapter is required.

Step 01 result: inventory completed. No production code was changed. Focused tests for any future implementation remain mandatory in their planned steps.


### STEP 01 — Existing Code and Data Inventory
- Inspect accepted Chapter 01 Core, Data, Service, UI and tests.
- Identify reusable daily breadth calculation and UDiFF/MII service methods.
- Record existing schemas and gaps before writing code.
- Test: inventory assertions and no-duplicate-module review.
- Exit: approved implementation map.

### STEP 02 — Historical Point-in-Time Universe Contract
- Define per-date MII snapshot requirements and identity keys.
- Define how a missing or unavailable historical MII snapshot blocks verified output.
- Test aligned, stale, future, mixed-date and missing snapshots.
- Exit: documented point-in-time membership contract.

### STEP 03 — Historical Observation Retrieval
- Reuse existing NSE UDiFF downloader and Bhavcopy service.
- Retrieve only requested NSE CM / STK / EQ observations.
- Preserve archive hash and actual fetch timestamp per date.
- Test retrieval failure, corrupt archive, wrong trade date and source provenance.
- Exit: validated date-indexed observations.

### STEP 04 — Prior-Session Price Validation
- Validate Previous Close and Current Close for each eligible identity.
- Confirm that the supplied Previous Close is the exchange-reported prior-session close; do not assume the prior calendar day is a trading day.
- Test weekends, holidays, missing rows, invalid prices and duplicate identities.
- Exit: deterministic daily comparison input.

### STEP 05 — Daily A/D Classification
- Reuse existing classification rules where suitable.
- Produce advances, declines, unchanged and missing counts per date.
- Test equality boundaries, zero movement, missing observations and exact universe reconciliation.
- Exit: tested daily A/D result.

### STEP 06 — A-D Difference and A/D Ratio
- Calculate A-D Difference and ratio.
- Define zero-decliner and zero-advancer states explicitly.
- Test division-by-zero, numeric finiteness and ratio correctness.
- Exit: no NaN/Infinity or silent capping.

### STEP 07 — Cumulative A-D Line
- Build a date-ordered cumulative series from daily A-D differences.
- Define initial anchor and reset behavior explicitly.
- Do not bridge missing/invalid dates without a documented policy.
- Test ordering, gaps, reset, reproducibility and REVIEW propagation.
- Exit: deterministic cumulative series.

### STEP 08 — Core Analysis Module
- Implement pure calculations only; no network or Streamlit imports.
- Return metrics, per-date status, coverage and provenance references.
- Test independent calculations and invalid-input rejection.
- Exit: Core test suite passes.

### STEP 09 — Market Intelligence Service
- Orchestrate existing Data adapters and Core calculations.
- Preserve per-date source, fetch timestamp, archive hash, fallback reason and MII evidence.
- Return PASS / REVIEW / BLOCKED / UNAVAILABLE honestly.
- Test service orchestration and failure propagation.
- Exit: service tests pass.

### STEP 10 — UI Integration
- Add Historical Advance / Decline view to the existing Market Intelligence page.
- Provide date range selection, counts, A-D Difference, ratio, cumulative line and coverage status.
- Display REVIEW dates visibly; do not render provisional series as verified PASS.
- Keep existing Market Regime, Breadth and other app navigation unchanged.
- Test UI/service integration and existing-page regression.
- Exit: UI integration tests pass.

### STEP 11 — Final Verification and Acceptance
- Run focused Chapter 02 tests.
- Run full TradeLab Pro regression.
- Run Yahoo adapter regression.
- Run live NSE UDiFF/MII verification for a selected valid trading date/range.
- Review generated evidence and compare all counts against source rows.
- Update Chapter 02 acceptance register and checkpoint.
- Exit: all mandatory implementation gates PASS; live coverage may remain REVIEW only if accurately disclosed and excluded from verified conclusions.

## 6. Chapter 02 Acceptance Gates

Chapter 02 cannot be accepted until:
- Point-in-time historical universe handling is verified.
- Historical daily data is sourced from approved adapters.
- Identity and coverage are validated for each date.
- Daily A/D counts match independently calculated test fixtures.
- A-D Difference and A/D Ratio are finite and correct.
- Cumulative A-D Line is deterministic and gap-aware.
- Missing observations are never treated as unchanged.
- PASS / REVIEW / BLOCKED / UNAVAILABLE states are correctly propagated.
- UI displays source and coverage status.
- Existing Market Regime and Breadth remain regression-safe.
- GitHub Actions pass.
- Evidence and checkpoint are recorded.

## 7. Out of Scope

- Sector Strength and sector mapping expansion.
- Index Participation.
- New Market Trend Classification beyond the existing Regime module.
- News and Events Context.
- BSE.
- F&O.
- Trading signals, buy/sell recommendations or fabricated market data.

These remain separate roadmap items and require their own chapter plans and acceptance gates.

## 8. Checkpoint

Checkpoint ID: `TLP-CP-2026-11-14-TLP-MIM-001-CH02-PLAN-DRAFT`

- Chapter 01: ACCEPTED WITH REVIEW CONDITIONS.
- Chapter 02: PLAN DRAFT — implementation not started.
- Sector Mapping Expansion: OFF.
- BSE: DISABLED.
- F&O Scanner: EXCLUDED.

This document is a plan draft. It does not activate Chapter 02 code or approve any live data result.

End of Chapter 02 Plan.
