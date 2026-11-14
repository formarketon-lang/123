# TLP-MIM-001 — Chapter 02 Plan
Project ID: TLP-MIM-001  
Parent Project: TLP-MASTER-001  
Repository: formarketon-lang/123  
Base: main  
Branch: ch02-advance-decline-plan  
Chapter: 02  
Title: Historical Advance / Decline Analysis  
Status: STEP 01–11 TECHNICAL VERIFICATION COMPLETE; CHAPTER ACCEPTANCE HELD FOR REVIEW CONDITIONS  
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

Status: CONTRACT + AUTOMATED TEST COVERAGE VERIFIED — STRICT DATE-ALIGNMENT GATE

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

Step 02 result: the 12-scenario contract matrix now has automated coverage in the existing NSE MII reconciliation and universe-provider tests. The mapped test functions are recorded in the Chapter 02 Acceptance Register. Stale/previous-date MII snapshots are rejected before verified output; this is deliberately stricter than allowing a diagnostic REVIEW result and prevents stale membership from entering historical A/D. The official MII archive hash and fetch timestamp are now exposed per requested date. NSE does not supply a publication timestamp in the retrieved archive response, so strict point-in-time availability remains REVIEW. Multi-date orchestration is implemented in Step 03.

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

Status: PASS — FULL REGRESSION VERIFIED

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

Status: PASS — FULL REGRESSION VERIFIED

Implementation:
- Added `core/market_intelligence/cumulative_ad_line.py`.
- Added `calculate_cumulative_ad_line(metrics, expected_sessions, initial_anchor=0)`.
- Requires an explicit, verified NSE session calendar supplied by the caller; no weekend/holiday inference or Yahoo calendar substitution.
- Calculates cumulative A-D from daily A-D Difference in chronological session order.
- Default initial anchor is 0; caller may provide an integer anchor.
- PASS sessions contribute to the line.
- Missing, REVIEW, BLOCKED and UNAVAILABLE sessions emit null cumulative values and break the segment. The next PASS session starts a new segment from the configured anchor.
- Metrics dates outside the verified calendar, duplicate dates, invalid statuses and non-integer PASS differences are rejected.
- Integer-valued floats from nullable Pandas columns are accepted only when finite and mathematically integral.

Tests:
- Added `tests/test_market_intelligence_cumulative_ad_line.py`.
- 12 test functions plus 3 parametrized cases (15 cases) cover accumulation, initial anchor, missing session reset, REVIEW/BLOCKED/UNAVAILABLE resets, nullable DataFrame values, calendar validation, duplicates, invalid values, deterministic output and empty calendars.

Limitations:
- This step does not fetch or authenticate the official NSE calendar; the caller must supply verified sessions.
- A missing date can only be identified when it is present in the supplied expected-session calendar.
- No live historical date range or UI integration is claimed.

Exit: implementation and 15 test cases pass in GitHub Actions; TradeLab Pro full regression 687 passed and Yahoo Adapter workflow PASS.

### STEP 08 — Core Analysis Module

Status: PASS — FULL REGRESSION VERIFIED

Implementation:
- Added `core/market_intelligence/historical_ad_analysis.py`.
- Added `analyze_historical_advance_decline(history, expected_sessions, initial_anchor=0)`.
- Pure orchestration only; imports no network client, data provider or Streamlit.
- Reuses Step 05 daily classifier, Step 06 daily metrics and Step 07 cumulative line; no duplicate calculations.
- Returns daily classification, A-D metrics, cumulative line, combined per-date status, coverage table and source provenance table.
- Retains source, URL, filename, SHA-256, fetch timestamp and MII snapshot date by observation date.
- Includes missing expected sessions explicitly as MISSING; missing sessions affect overall REVIEW and break cumulative segments.
- Preserves REVIEW, BLOCKED and UNAVAILABLE without fabricating counts or metrics.

Tests:
- Added `tests/test_market_intelligence_historical_ad_analysis.py`.
- 12 focused tests cover output contract, source provenance, missing-session handling, REVIEW/BLOCKED/UNAVAILABLE propagation, duplicate/out-of-calendar/wrong-date rejection, anchor handling and pure-module import boundaries.

Limitations:
- Requires caller-supplied verified NSE session calendar and already retrieved historical observations.
- Does not fetch NSE data or connect Streamlit UI.
- Live historical date-range validation remains pending.

Exit: implementation and 12 focused tests pass in GitHub Actions; TradeLab Pro full regression 699 passed and Yahoo Adapter workflow PASS.

### STEP 09 — Market Intelligence Service

Status: PASS — FULL REGRESSION VERIFIED

Implementation:
- Added `services/market_intelligence/historical_ad_service.py`.
- Added `analyze_nse_historical_advance_decline(expected_sessions, initial_anchor=0, session=None)`.
- Reuses `retrieve_nse_historical_observations` and the pure Step 08 core API; no duplicate downloader, provider or classifier.
- Caller supplies the verified NSE session dates. The existing historical retriever attempts each date independently.
- Preserves retrieval status, requested dates, retrieval summary and per-date provenance (source URL, filename, SHA-256, fetch timestamp and MII snapshot date) through the core result.
- Per-date UNAVAILABLE/BLOCKED/REVIEW conditions remain visible; retrieval exceptions are propagated, not silently converted into fabricated results.
- Session injection is supported for deterministic tests and controlled NSE retrieval.

Tests:
- Added `tests/test_market_intelligence_historical_ad_service.py`.
- 8 test functions plus 2 parametrized cases (10 cases) cover retriever/core reuse, caller arguments, retrieval status, exception propagation, invalid/empty requests and date-list handling.

Limitations:
- Verified session calendar remains caller-supplied; official NSE calendar integration is not added here.
- Existing historical retrieval is NSE UDiFF + dated MII; no Yahoo membership substitution or second downloader.
- No live historical date-range run or Streamlit UI integration is claimed.

Exit: implementation and 10 focused test cases pass in GitHub Actions; TradeLab Pro full regression 708 passed and Yahoo Adapter workflow PASS.

### STEP 10 — UI Integration

Status: PASS — GITHUB ACTIONS VERIFIED

- Integrated Historical A/D Analysis into `ui/market_intelligence.py`; existing Regime, Breadth and navigation retained.
- Requires explicit ISO NSE session dates; no weekday/holiday inference; maximum 30 sessions per request.
- Displays daily metrics, A-D Difference, A/D Ratio, cumulative chart, coverage and source/MII provenance.
- PASS / REVIEW / BLOCKED / UNAVAILABLE remain distinct; missing observations are never filled.
- Added 4 focused UI tests.
- GitHub Actions TradeLab Pro run #531: **712 passed**.
- Yahoo Adapter run #349: **PASS**.
- Official calendar automation and live historical verification remain pending.

Exit: Step 10 implementation and regression verified.

### STEP 11 — Final Verification and Acceptance

Status: PASS WITH LIVE REVIEW CONDITION — GITHUB ACTIONS VERIFIED

Implementation:
- Added `scripts/run_ch02_historical_ad_live_check.py` and `.github/workflows/ch02-historical-ad-live-check.yml`.
- Latest full TradeLab Pro regression: **714 passed**.
- Latest Yahoo Adapter regression: **56 passed**.
- Live NSE verification workflow completed successfully; run `43561818820`; evidence artifact uploaded and reviewed.
- Official NSE CM Bhavcopy date: 2026-11-13; dated MII snapshot also 2026-11-13.
- Bhavcopy archive SHA-256: `758ec3b60fd492a29ff3ebc6c069269bc326dc5ca662cfba8892f16939841b7b`.
- Fetched at UTC: `2026-11-14T05:30:35.075915Z`.
- Expected universe 2,762; verified 2,742; missing 20; identity exceptions 2; coverage 99.2759%.
- Verified-subset daily counts: Advancing 938, Declining 1,776, Unchanged 28; A-D Difference -838; A/D Ratio 0.5281531532.
- Live data status is **REVIEW**, not PASS. The 2,742 verified observations reconcile; the 20 missing members and 2 identity exceptions keep the full date in REVIEW. Cumulative A-D is not emitted for this REVIEW session.
- Added formal register: `docs/architecture/market_intelligence_ch02_acceptance_register.md`.

Acceptance conditions still open:
- Official NSE calendar retrieval/authentication is not implemented; verified sessions remain caller-supplied.
- Only a one-session live smoke test has been run; multi-month historical-range verification remains pending.
- Raw dated MII archive SHA-256 and fetch timestamp are not yet exposed in the production historical service.
- Step 02's 12 cases remain a documented contract matrix, not 12 automated tests.

Exit: Step 11 technical verification PASS with explicit live REVIEW condition. Chapter 02 is not marked fully accepted until the open point-in-time evidence gaps are closed or explicitly approved as review conditions.

### STEP 11 — Final Verification and Acceptance

Status: TECHNICAL WORKFLOW PASS; MULTI-MONTH EVIDENCE REVIEWED WITH COVERAGE LIMIT

Latest regression:
- TradeLab Pro full regression: **727 passed** (PR workflow run 43563135790).
- Yahoo Adapter regression: **56 passed** (PR workflow run 43563135837).
- No failures in the latest PR regression runs.

NSE calendar and range evidence:
- The official NSE holiday master redirect validation now accepts the official nseindia.in host as well as nseindia.com.
- Calendar evidence: status PASS; official NSE source URL, raw-response SHA-256 and UTC fetch timestamp are present.
- 120-calendar-day request: 2026-07-17 through 2026-11-13.
- Official calendar found **83** NSE CM sessions, including one archive-verified special session on 2026-11-08.
- First range run analyzed only the latest **60 of 83** sessions because the workflow default was 60. Its workflow passed and uploaded an artifact, but it is not full 120-day session coverage.
- Across those 60 sessions: 60 REVIEW, 0 PASS; 161,172 expected member-observations, 160,428 verified, 744 missing and 231 identity exceptions. Coverage ranged 98.4341%–99.9251%, mean 99.5397%.
- The daily A-D values are verified-subset diagnostics only; no date is promoted to full-universe PASS.
- Bhavcopy and MII source URL, filename, SHA-256, fetched-at UTC and dated MII snapshot are all present in the range retrieval summary for all 60 analyzed sessions. The MII publication timestamp remains unavailable, so strict point-in-time status is REVIEW.
- Corrected workflow and script defaults to max_sessions=180, so the next run will analyze all sessions in the requested 120-day range rather than silently truncating at 60.

Step 02 automated scenario coverage:
- The 12 contract scenarios are mapped to existing focused tests; 16 reconciliation test functions cover the matrix, plus MII raw-provenance tests.
- A stale/previous-date snapshot is rejected before verified output (strict no-look-ahead gate); it is not silently substituted.
- Publication timestamp unknown is explicitly tested as point-in-time REVIEW.

Open acceptance conditions:
- Await the new full 83-session live range run and review its artifact.
- The NSE source does not provide an official publication timestamp in the retrieved MII response; strict point-in-time availability remains REVIEW.
- Live universe reconciliation has missing members and identity exceptions; no full-universe PASS is claimed.

Exit: Step 11 technical verification is progressing; the 60-session evidence run passed as a workflow but did not cover all 83 sessions. Chapter 02 remains unaccepted until the corrected full-range artifact is reviewed and the point-in-time REVIEW condition is explicitly accepted or resolved.

## 5A. Step 11 — Full 83-session artifact review (2026-11-14)

Completed range evidence:
- Workflow run: 43563688178 — SUCCESS.
- Artifact ID: 14101766488.
- Artifact SHA-256: ff11eda60daa9f8e7d7fae882ab6c6ba3b5884617365e9c4584a9b4a1eaf63d9.
- Requested period: 2026-07-17 to 2026-11-13 (120 calendar days).
- Official NSE CM sessions discovered and analyzed: 83/83.
- Calendar: PASS; 2026-11-08 special session supported by an official NSE archive.
- All 83 Bhavcopy and dated MII records have raw SHA-256 and actual UTC fetch timestamps; each MII snapshot date matches its observation date.
- All 83 sources are NSE. The retrieved MII response supplies no official publication timestamp; strict point-in-time status remains REVIEW.

Aggregate reconciliation:
- Expected member-observations: 217,464.
- Verified member-observations: 216,334.
- Missing: 1,130.
- Identity exceptions: 288.
- Mean daily coverage: 99.4834%; range: 93.3257%–99.9251%.
- Daily statuses: 83 REVIEW, 0 PASS.

Coverage exceptions requiring authoritative investigation:
- 2026-08-14: 176 missing; 93.3257% coverage.
- 2026-08-10: 51 missing; 16 identity exceptions.
- 2026-11-02: 43 missing; 11 identity exceptions.
- 2026-10-29: 24 identity exceptions.

All daily A-D metrics remain verified-subset diagnostics. The cumulative A-D value is null across all 83 sessions because non-PASS sessions must not be combined into a verified cumulative series. No REVIEW date is promoted to PASS.

The range artifact was reviewed directly from its ZIP contents. A subsequent service-default alignment workflow, run 43564379235, was still IN PROGRESS at checkpoint review. The completed 83-session artifact already passed max_sessions=180 explicitly; recheck the alignment run before final acceptance.

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

Checkpoint ID: TLP-CP-2026-11-14-TLP-MIM-001-CH02-STEP-11-RANGE-VERIFICATION-IN-PROGRESS

- Chapter 01: ACCEPTED WITH REVIEW CONDITIONS; remains separate.
- Steps 01–11: implementation and technical verification recorded; Chapter 02 acceptance remains held for full-range evidence and point-in-time REVIEW.
- Step 02: 12-scenario contract matrix mapped to 16 focused reconciliation test functions plus MII provenance tests. Stale snapshots are rejected before verified output.
- Step 06: A-D Difference and A/D Ratio — PASS; 17 focused cases.
- Step 07: Cumulative A-D Line — PASS; 15 focused cases.
- Step 08: Core Analysis — PASS; 12 focused cases.
- Step 09: Historical A/D Service — PASS; 10 focused cases.
- Step 10: UI Integration — PASS; 4 focused UI tests.
- Latest PR regression on commit 35ab609c7ae524bc10b18c36b7cf83e412c79c99: TradeLab Pro **727 passed** (run 43564395698); Yahoo Adapter **56 passed** (run 43564395706).
- Official NSE Calendar: implemented; 120-day calendar evidence PASS, 83 sessions discovered, one special session archive-verified.
- Corrected full-range artifact 14101766488 (run 43563688178): 83/83 sessions analyzed; all 83 REVIEW; 217,464 expected, 216,334 verified, 1,130 missing and 288 identity exceptions; mean coverage 99.4834%.
- Bhavcopy and MII raw SHA-256 plus actual fetched-at UTC are present for all 83 dates; all MII snapshot dates align. MII publication timestamp unavailable; strict point-in-time status remains REVIEW.
- Workflow, script and historical service defaults are aligned to 180 sessions. Alignment workflow run 43564379235 was IN PROGRESS at last check; completed 83-session artifact already verified the full range.
- Latest Actions page: https://github.com/formarketon-lang/123/actions
- PR #2: DRAFT / UNMERGED; Main unchanged.
- Sector Mapping Expansion: OFF. BSE: DISABLED. F&O Scanner: EXCLUDED.

Chapter 02 is not declared accepted. The full 83-session artifact is reviewed, but all dates remain REVIEW. Recheck alignment workflow 43564379235 and resolve or explicitly accept the MII publication-time and universe-reconciliation review gates; never convert REVIEW data into PASS.

End of Chapter 02 Plan.
