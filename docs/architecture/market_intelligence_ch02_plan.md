# TLP-MIM-001 — Chapter 02 Plan
Project ID: TLP-MIM-001  
Parent Project: TLP-MASTER-001  
Repository: formarketon-lang/123  
Base: main  
Branch: ch02-advance-decline-plan  
Chapter: 02  
Title: Historical Advance / Decline Analysis  
Status: CHAPTER PLAN DRAFT — STEPS 01–05 VERIFIED; STEP 06 IMPLEMENTED; CI PENDING  
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

Status: INVENTORY VERIFIED — NO CODE CHANGE

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


### STEP 02 — Historical Point-in-Time Universe Contract

Status: CONTRACT DEFINED — REVIEW GATE; IMPLEMENTATION NOT STARTED

#### 2.1 Purpose and population

The Chapter 02 breadth population is the complete NSE Capital Market cash-equity security universe that is eligible for the selected trade date, restricted to the official `EQ` series. It is not an index constituent list and must not be described as one. BSE, SME/other series, derivatives, ETFs or other instruments are excluded unless a separately approved scope change explicitly adds them.

#### 2.2 Required snapshot identity and provenance

Every daily population snapshot must carry, at minimum:

- `Exchange`: exactly `NSE`.
- `Segment`: exactly `CM` (Capital Market).
- `Series`: exactly `EQ`.
- `Universe As Of Date`: the effective NSE business/trade date for which the membership is asserted.
- `Source`: official NSE MII/security-master source identifier; Yahoo is never a membership source.
- `Source URL or archive reference`: stable retrieval reference to the official NSE source.
- `Published At`: official publication timestamp when supplied by NSE; otherwise explicitly null/unknown.
- `Fetched At UTC`: actual retrieval timestamp, timezone-aware.
- `Archive SHA-256`: hash of the exact downloaded raw source bytes.
- `Schema / parser version`: version used to interpret the source.
- `Universe Verification Status`: `MII_DATED` only after all required checks pass.
- Identity keys: normalized Symbol and ISIN; Instrument ID is mandatory for comparison whenever it is supplied by both the source snapshot and the Bhavcopy.

A file name, a manually entered date, a cached current security list, or a hash without the original raw bytes is not sufficient evidence of an official dated snapshot.

#### 2.3 Date alignment and no-look-ahead rules

1. Each A/D observation date must resolve to one and only one NSE CM / EQ universe snapshot whose `Universe As Of Date` exactly equals that observation's NSE trade date.
2. A future-dated snapshot is `BLOCKED`; it must never be used for an earlier observation.
3. A stale/previous-date snapshot is `REVIEW` at most for diagnostic comparison and is not eligible to produce a verified historical A/D result.
4. A snapshot with mixed effective dates, missing effective dates, unknown source provenance, invalid hash, or unverified parser/schema is `BLOCKED` or `UNAVAILABLE` according to whether contradictory evidence exists or evidence is simply absent.
5. Do not carry the current MII universe backward across history. Do not forward-fill membership across dates, holidays, missing files, or source outages.
6. If NSE does not provide an official historical snapshot for a requested date, report that date as `UNAVAILABLE`; do not infer membership from Yahoo, current listings, or a later snapshot.
7. For strict point-in-time claims, if the official publication timestamp is unavailable or is later than the observation date, the date cannot be represented as historically knowable on that date. Preserve the effective-date result but mark point-in-time availability `REVIEW` until the publication-time evidence is resolved. Do not silently claim a no-look-ahead PASS.

#### 2.4 Identity and reconciliation contract

- Normalize identity strings by trim + uppercase only; do not perform fuzzy symbol matching.
- Symbol and ISIN must both match between the daily NSE CM/EQ Bhavcopy row and the same-date official MII snapshot.
- When Instrument ID exists in both sources, it must also match. If present in only one source, reject the comparison as `BLOCKED`; do not silently downgrade to Symbol-only.
- Duplicate Symbol, duplicate ISIN, duplicate Instrument ID, blank identity, malformed ISIN, non-NSE exchange, non-CM segment, or non-EQ series blocks that snapshot/date.
- A Bhavcopy row absent from the dated universe is an identity exception: exclude it from verified counts and mark the date `REVIEW`.
- A universe member with no valid daily observation is a missing observation, not unchanged. Count it as missing and reduce coverage.
- Do not infer a security's historical listing/delisting date from today's security master.

#### 2.5 Coverage and status semantics

Let:
- `N_expected` = unique valid members in the official dated NSE CM/EQ snapshot.
- `N_verified` = expected members with a valid same-date Bhavcopy observation and all required identity keys matched.
- `N_missing` = expected members without a valid same-date observation.
- `N_exception` = observed Bhavcopy rows that fail dated-universe identity reconciliation.

Coverage = `100 * N_verified / N_expected` when `N_expected > 0`; otherwise coverage is null and status is `UNAVAILABLE`.

- `PASS`: dated snapshot provenance and date alignment verified; all identity keys pass; `N_missing = 0`; `N_exception = 0`; coverage = 100%.
- `REVIEW`: a valid dated snapshot exists but one or more members are missing, an observed identity exception exists, or strict publication-time evidence is unresolved. Only the verified subset may be described as verified; never imply the full universe was covered.
- `BLOCKED`: contradictory or invalid evidence (future/mixed date, duplicate identities, invalid source/hash/schema, invalid exchange/segment/series, or key mismatch that the current validator treats as fatal) prevents calculation for that date.
- `UNAVAILABLE`: no authoritative dated snapshot or required daily source file is available; no verified breadth result is emitted.

A percentage alone never upgrades a date to PASS. No arbitrary tolerance (including 99% or 99.9%) may turn incomplete coverage into PASS.

#### 2.6 Historical contract test matrix

Before Step 02 can be marked fully PASS, tests must cover:

| Case | Expected result |
|---|---|
| Exact same-date official NSE CM/EQ snapshot, valid provenance, all identities matched, no missing rows | PASS |
| Previous-date snapshot | REVIEW; not eligible for verified historical output |
| Future-date snapshot | BLOCKED |
| Mixed snapshot dates or a missing row-level effective date | BLOCKED |
| Missing official historical snapshot | UNAVAILABLE |
| Publication timestamp unknown or after observation date | REVIEW for strict point-in-time availability |
| Symbol matches but ISIN differs | Exclude row; REVIEW/BLOCKED per validator contract |
| Instrument ID present on only one side | BLOCKED |
| Duplicate Symbol / ISIN / Instrument ID | BLOCKED |
| Expected universe member absent from Bhavcopy | Count missing; REVIEW |
| Bhavcopy row not present in dated universe | Exclude as exception; REVIEW |
| Yahoo or current-universe substitution for NSE membership | BLOCKED |

Step 02 result: contract documented. This is a specification milestone only; no production implementation or test suite is claimed complete. The exact-date rule is consistent with the current single-date MII reconciliation, while publication-time availability and multi-date orchestration remain implementation gaps for later steps.

### STEP 03 — Historical Observation Retrieval

Status: PASS — IMPLEMENTED ON FEATURE BRANCH; GITHUB ACTIONS VERIFIED

Implementation:
- Added `services/market_intelligence/historical_observation_service.py`.
- Reuses the existing `analyze_nse_market_breadth_from_udiff` production service once per requested date.
- Sorts dates chronologically and rejects empty input, malformed dates, duplicate dates and a single string passed instead of an iterable.
- Keeps each date's NSE Bhavcopy source URL, archive filename, SHA-256, actual fetch timestamp, MII snapshot date, coverage and identity counts.
- Retains per-date verified and unverified observations separately.
- Records a failed date as `UNAVAILABLE` and continues to the next requested date; no previous/next date data or MII universe is carried over.
- Overall status precedence is `BLOCKED` → `UNAVAILABLE` → `REVIEW` → `PASS`, so a missing requested date cannot be hidden by a REVIEW date.
- Aggregates verified observations in date/Symbol order and exposes a per-date summary table.

Tests added:
- `tests/test_market_intelligence_historical_observation_service.py`
- Covers date sorting, malformed/empty/duplicate input, per-date provenance, failure isolation, REVIEW propagation, no cross-date reuse and mixed-status precedence.
- Eight test functions plus five parameterized invalid-date cases are defined; the full TradeLab Pro workflow passed (626 tests), and Yahoo Adapter workflow passed (56 tests).

Limitations and safety:
- This step retrieves historical NSE observations only; it does not calculate the A/D series.
- The existing single-date service remains responsible for same-date NSE MII validation and UDiFF provenance audit.
- The current MII fetcher does not expose the raw MII archive SHA-256 / fetch timestamp in its returned DataFrame; this remains an evidence gap and must not be claimed complete by this step.
- No live historical date range has been executed in this step.
- No production UI or Main branch change.

Exit: implementation and focused tests are committed to the Chapter 02 draft branch; full regression and Yahoo adapter workflows both PASS. Live historical-range verification is still pending.

### STEP 04 — Prior-Session Price Validation

Status: VALIDATION ENGINE PASS — GITHUB ACTIONS VERIFIED; OFFICIAL CALENDAR INTEGRATION PENDING

Implementation:
- Added `services/market_intelligence/prior_session_validation.py`.
- Compares each requested date's NSE `Previous Close` with the same Symbol + ISIN's `Current Close` from the immediately preceding session in a caller-supplied, independently verified NSE trading calendar.
- Uses the repository's existing price tolerance of 0.01; the global data-integrity tolerance is not changed.
- Requires explicit target observation dates so a warm-up prior-session row is not incorrectly treated as another date to validate.
- Handles weekend gaps, official holidays and special sessions strictly through the supplied calendar; no Monday-Friday inference or calendar-day subtraction.
- Missing entire prior-session archive is `UNAVAILABLE`; missing one security's prior observation is `REVIEW`; identity conflicts, duplicate identities, invalid prices or price differences beyond tolerance are `BLOCKED`.
- Returns per-symbol differences and per-date counts/status for downstream deterministic A/D processing.

Tests added:
- `tests/test_market_intelligence_prior_session_validation.py`
- 15 focused test functions cover prior-session equality, holiday/weekend gaps, special sessions, tolerance boundaries, missing prior rows, ISIN mismatch, unavailable archives, unverified calendar, duplicate dates/identities and invalid prices.

Important limitations:
- This module validates against a supplied calendar; it does not yet download or independently authenticate the official NSE trading calendar.
- The caller must include at least one prior-session warm-up observation before the first target date.
- No live historical NSE range has been run.
- The MII raw archive SHA-256 / fetch timestamp gap from Step 03 remains open.
- This is a pure validation module; no production UI, live service activation or Main branch change.

Exit: deterministic validation engine and focused tests pass in GitHub Actions. Official calendar-source integration and live historical verification remain pending.

### STEP 05 — Daily A/D Classification

Status: PASS — 15 FOCUSED TESTS; FULL REGRESSION VERIFIED

Implementation:
- Added `core/market_intelligence/advance_decline.py`.
- Reuses `core.market_intelligence.breadth.analyze_market_breadth` for the established price-direction classification; no duplicate comparison engine was introduced.
- Consumes the date-isolated output of `retrieve_nse_historical_observations` and classifies only its verified observations.
- Produces per-date Advancing, Declining, Unchanged, Missing, Identity Exceptions, Verified Observations, Expected Universe, Coverage and status.
- Missing members are counted separately and never added to Unchanged. If all observations are missing, the result is 0/0/0 plus the full missing count and REVIEW.
- REVIEW dates may show verified-subset counts but remain REVIEW. BLOCKED and UNAVAILABLE dates never receive fabricated classification counts.
- Enforces count reconciliation, unique dates, supported status values, verified-observation row counts, exact observation-date isolation and valid coverage values.
- Overall status precedence is BLOCKED → UNAVAILABLE → REVIEW → PASS.

Tests added:
- `tests/test_market_intelligence_advance_decline.py`
- 15 focused tests cover advances/declines/unchanged, missing observations, all-missing dates, identity exceptions, unavailable/blocked dates, date ordering, duplicate dates, metadata mismatch, exact date isolation and invalid prices.

Limitations:
- This is a pure historical classification layer; it does not fetch NSE data or calculate A-D Difference, A/D Ratio or cumulative A-D Line.
- Official NSE calendar integration, MII raw archive provenance exposure and live historical-range verification remain open.
- No production UI or Main branch change.

Exit: implementation and 15 focused tests pass in GitHub Actions; full TradeLab Pro regression 656 passed and Yahoo Adapter regression 56 passed.

### STEP 06 — A-D Difference and A/D Ratio

Status: IMPLEMENTED ON FEATURE BRANCH — GITHUB ACTIONS PENDING

Implementation:
- Added `core/market_intelligence/ad_metrics.py`.
- Added `calculate_historical_ad_metrics`, consuming the existing Step 05 classification summary; no duplicate daily classifier or data retrieval.
- A-D Difference = Advancing - Declining.
- A/D Ratio = Advancing / Declining only when Declining > 0.
- Zero Decliners: ratio is null with `NO_DECLINERS`; no Infinity or silent cap.
- Zero Advancers with Decliners present: ratio is exactly 0 with `NO_ADVANCERS`.
- Both Advancing and Declining zero: ratio is null with `NO_ADVANCES_OR_DECLINES`.
- REVIEW rows calculate metrics only for the verified subset and remain REVIEW.
- BLOCKED / UNAVAILABLE rows receive no fabricated A-D metrics.
- Enforces non-negative integer counts, exact reconciliation against verified observations, unique dates, chronological output and finite ratio values; overflow is rejected.

Tests added:
- `tests/test_market_intelligence_ad_metrics.py`
- 13 test functions plus 6 parametrized cases (17 cases total) cover normal calculations, zero-decliner, zero-advancer, no movers, REVIEW behavior, BLOCKED/UNAVAILABLE, reconciliation, invalid counts, duplicate dates, chronological ordering, status precedence and unsupported status rejection.

Limitations:
- This step calculates daily A-D Difference and A/D Ratio only; cumulative A-D Line is Step 07.
- It consumes Step 05 output and does not retrieve NSE data or activate UI.
- No live historical date range, official NSE calendar integration or MII raw archive provenance completion is claimed.
- No Main branch change.

Exit: implementation and 18 test cases committed to the draft feature branch; GitHub Actions verification pending.

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

Checkpoint ID: `TLP-CP-2026-11-14-TLP-MIM-001-CH02-STEP-06-AD-METRICS-CI-PENDING`

- Chapter 01: ACCEPTED WITH REVIEW CONDITIONS.
- Chapter 02: PLAN + STEP 01 INVENTORY + STEP 02 UNIVERSE CONTRACT DOCUMENTED.
- Step 03 status: REGRESSION PASS; feature branch remains unmerged.
- Step 04: prior-session validation engine and 15 focused tests PASS in GitHub Actions.
- Step 05: daily A/D classification PASS; 15 focused tests. Latest verified GitHub Actions: TradeLab Pro 656 passed; Yahoo Adapter 56 passed.
- Step 06: A-D Difference and A/D Ratio implementation added; 17 test cases committed; oversized-number test replaced with unsupported-status contract test after Pandas coerced the impossible fixture before metric calculation; fresh GitHub Actions verification pending.
- Official NSE calendar downloader/authentication: NOT IMPLEMENTED; caller-supplied verified calendar required.
- Live historical-range validation: NOT RUN.
- Step 03: historical retrieval orchestration and focused tests added on the draft feature branch.
- Step 03 full TradeLab Pro regression: PASS — 626 tests.
- Step 03 Yahoo Adapter regression: PASS — 56 tests.
- Step 03 live historical-range verification: NOT RUN.
- MII raw archive SHA-256 / fetch timestamp exposure: REMAINS AN EVIDENCE GAP.
- Sector Mapping Expansion: OFF.
- BSE: DISABLED.
- F&O Scanner: EXCLUDED.

This document is a plan draft. It does not activate Chapter 02 code or approve any live data result.

End of Chapter 02 Plan.
