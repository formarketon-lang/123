# TLP-MIM-001 — Chapter 02 Acceptance Register

Project: TLP-MIM-001  
Parent: TLP-MASTER-001  
Repository: formarketon-lang/123  
Branch: ch02-advance-decline-plan  
Base: main  
Chapter: 02 — Historical Advance / Decline Analysis  
Checkpoint: TLP-CP-2026-11-14-TLP-MIM-001-CH02-STEP-11-RANGE-VERIFICATION-IN-PROGRESS  
Register status: FULL 83-SESSION RANGE EVIDENCE REVIEWED; POINT-IN-TIME AND UNIVERSE COVERAGE REVIEW GATES OPEN  
PR: #2 — Draft / Unmerged

---

## 1. Step acceptance

| Step | Scope | Status | Evidence |
|---|---|---|---|
| 01 | Existing architecture inventory | PASS | Existing NSE UDiFF/MII/breadth path reused; no duplicate downloader |
| 02 | Point-in-time NSE CM/EQ universe contract | AUTOMATED TEST COVERAGE VERIFIED; REVIEW SEMANTICS DOCUMENTED | 12 scenarios mapped to 16 focused reconciliation tests plus MII provenance tests |
| 03 | Historical observation retrieval | PASS | Existing single-date NSE service orchestrated per requested date |
| 04 | Prior-session validation | PASS | Explicit verified-session calendar contract and focused tests |
| 05 | Daily A/D classification | PASS | Existing breadth classifier reused; missing is not unchanged |
| 06 | A-D Difference / A-D Ratio | PASS | 17 focused cases; zero-denominator state explicit |
| 07 | Cumulative A-D Line | PASS | 15 focused cases; non-PASS sessions break segments |
| 08 | Pure Core Analysis | PASS | 12 focused cases; provenance, coverage and status composition |
| 09 | Historical A/D Service | PASS | 10 focused cases; existing retriever reused |
| 10 | Market Intelligence UI | PASS | 4 focused UI tests |
| 11 | Final Verification | IN PROGRESS — FULL RANGE EVIDENCE REVIEWED | 83/83 official sessions analyzed; all 83 remain REVIEW due to incomplete universe reconciliation and unknown MII publication time |

## 2. Latest GitHub Actions verification

Latest PR regression commit: `181423957f28253059c5a41fb792ed7e7f9b917d`.

- TradeLab Pro Tests: **731 passed**, workflow run `43568642666`.
- Yahoo Adapter Unit Tests: **56 passed**, workflow run `43568642668`.
- Both latest PR workflows completed successfully; no failures in these latest runs.
- The additional two tests validate accurate range-report aggregation and safe handling of absent evidence frames.
- Earlier failures were found and corrected:
  - Historical live check rejected the official NSE redirect host `nseindia.in`; allowlist now accepts both official NSE domains.
  - Multi-month workflow initially failed due to its trigger/input configuration; the workflow was corrected and a later range run completed successfully.
- A successful workflow means the evidence job ran successfully. It does not promote REVIEW market data to PASS.

## 3. Official NSE calendar and first 120-day range evidence

Range workflow run: `43563070544`  
Workflow result: SUCCESS  
Artifact: `tlp-mim-ch02-multi-month-historical-ad-evidence`  
Artifact SHA-256: `926dc4c23034bdc987f07ee100cccc593fe73902c5a45082c6e9ff8f2f88ffd7`

Requested period:
- Start: 2026-07-17
- End: 2026-11-13
- Calendar days: 120
- Official NSE CM sessions discovered: **83**
- Special session archive-verified: 2026-11-08
- NSE holiday master status: PASS
- Holiday-master source SHA-256: `8903f442b9b3bef9bb1e835112ffae68faab995948d591adc9dcbd6ddd056d6a`
- Holiday-master fetched at UTC: `2026-11-14T05:46:02.142451Z`
- Final holiday-master URL: `https://www.nseindia.in/api/holiday-master?type=trading`

Coverage limit in the first artifact:
- The run analyzed only the latest **60 of 83** discovered sessions because the workflow default was 60.
- Analyzed dates: 2026-08-19 through 2026-11-13.
- All 60 analyzed dates were REVIEW; zero were PASS.
- Expected member-observations: **161,172**
- Verified member-observations: **160,428**
- Missing: **744**
- Identity exceptions: **231**
- Coverage range: **98.4341%–99.9251%**
- Mean daily coverage: **99.5397%**
- All A/D counts and ratios are verified-subset diagnostics only. No incomplete date is promoted to full-universe PASS.

MII provenance:
- For all 60 analyzed dates, the retrieval-summary CSV contains MII source URL, filename, raw archive SHA-256, actual fetched-at UTC, dated MII snapshot date and point-in-time status.
- Bhavcopy source URL, filename, SHA-256 and fetch timestamp are also present.
- The MII response does not provide an official publication timestamp. The point-in-time status therefore remains REVIEW; do not claim that the archive was provably published before the observation date.

## 4. Step 02 — Automated scenario test mapping

The 12 contract scenarios are covered by existing focused tests. The 16 reconciliation tests in `tests/test_nse_bhavcopy_mii_validation.py` include:

| Contract scenario | Automated test evidence |
|---|---|
| Exact same-date NSE CM/EQ identity and full coverage | `test_exact_mii_identity_and_full_coverage_pass` |
| Previous-date/stale snapshot | `test_wrong_snapshot_date_is_rejected`; rejected before verified output |
| Future-dated snapshot | `test_future_dated_mii_snapshot_is_rejected` |
| Mixed or missing row-level snapshot dates | `test_mixed_mii_snapshot_dates_are_rejected`; `test_partially_undated_mii_snapshot_is_rejected` |
| Missing official historical snapshot | `test_missing_official_historical_snapshot_is_unavailable` |
| Unknown publication timestamp | `test_fetcher_attaches_exact_mii_archive_hash_and_fetch_timestamp` in `tests/test_nse_universe.py`; asserts UNKNOWN and point-in-time REVIEW |
| Symbol matches but ISIN differs | `test_symbol_isin_mismatch_is_review_and_excluded` |
| Instrument ID present on only one side | `test_instrument_id_must_exist_in_both_sources` |
| Duplicate Symbol / ISIN / Instrument ID | `test_duplicate_symbol_is_rejected`; `test_duplicate_isin_in_universe_is_rejected`; `test_duplicate_instrument_id_in_mii_is_rejected` |
| Expected universe member missing from Bhavcopy | `test_missing_bhavcopy_symbol_is_review_not_fake_data` |
| Bhavcopy row absent from dated MII universe | `test_unknown_symbol_is_review_and_excluded_from_verified_observations` |
| Yahoo/current or undated-universe substitution | `test_yahoo_or_non_mii_universe_substitution_is_rejected`; `test_undated_mii_is_rejected` |

Strict-date note: stale/previous-date MII is rejected before verified A/D output. It is never substituted or treated as verified. The service's strict rejection may surface as unavailable at the historical retrieval boundary; this is intentionally conservative. Unknown publication time is retained as REVIEW.

## 5. Corrective action now committed

The first 120-day range had 83 official sessions but the default cap analyzed only 60. Corrected:
- `.github/workflows/ch02-historical-ad-range-check.yml`: default `max_sessions=180`.
- `scripts/run_ch02_historical_ad_range_check.py`: default `max_sessions=180`.

The next range workflow triggered by these changes must be checked for all 83 sessions and its new artifact reviewed before Step 11 can close.

## 5A. Corrected full 83-session range evidence — reviewed

Range workflow run: 43563688178  
Workflow result: SUCCESS  
Artifact: tlp-mim-ch02-multi-month-historical-ad-evidence  
Artifact ID: 14101766488  
Artifact SHA-256: ff11eda60daa9f8e7d7fae882ab6c6ba3b5884617365e9c4584a9b4a1eaf63d9

The artifact was downloaded and its JSON/CSV files were inspected directly.

- Requested period: **2026-07-17 through 2026-11-13** (120 calendar days).
- Official NSE CM calendar sessions: **83**; analyzed sessions: **83/83**.
- Calendar status: PASS; special session 2026-11-08 has an archive-verified NSE Bhavcopy.
- All 83 rows are NSE-sourced; all 83 dated MII snapshots match their observation dates.
- Bhavcopy SHA-256 and fetched-at UTC are present for all 83 dates.
- MII raw archive SHA-256 and fetched-at UTC are present for all 83 dates.
- MII publication timestamp is not supplied by the retrieved NSE source; all 83 point-in-time statuses remain REVIEW.

Universe reconciliation across 83 sessions:

| Measure | Result |
|---|---:|
| Expected member-observations | **217,464** |
| Verified member-observations | **216,334** |
| Missing observations | **1,130** |
| Identity exceptions | **288** |
| Mean daily coverage | **99.4834%** |
| Coverage range | **93.3257%–99.9251%** |
| Daily status | **83 REVIEW / 0 PASS** |

Notable coverage exceptions for investigation:
- 2026-08-14: 176 missing; 93.3257% coverage.
- 2026-08-10: 51 missing and 16 identity exceptions.
- 2026-11-02: 43 missing and 11 identity exceptions.
- 2026-10-29: 24 identity exceptions.

Daily A-D values and ratios are verified-subset diagnostics only. The cumulative A-D field is null for all 83 dates because non-PASS sessions must not be joined into a verified cumulative series. No incomplete date is promoted to PASS.

A subsequent alignment run (43564379235) was observed IN PROGRESS while this register was updated; it changes the service default to 180 sessions. The reviewed 83-session artifact above already used max_sessions=180 explicitly and covers the complete official session list. Recheck the alignment run before final acceptance.

## 5B. Range report aggregation correction — committed; rerun pending

Artifact 14102646012 from successful workflow run 43565284657 was inspected directly. The new symbol-level reconciliation CSV contains 1,398 rows:
- 1,110 `MISSING_EXPECTED_MEMBER`
- 268 `IDENTITY_EXCEPTION` (`SYMBOL_NOT_IN_VERIFIED_MII_UNIVERSE`)
- 20 `IDENTITY_EXCEPTION_NOT_VERIFIED` (`SYMBOL_ISIN_MISMATCH`)

The coverage CSV independently totals 1,130 missing member-observations and 288 identity exceptions. The 20 ISIN mismatch rows are deliberately represented as not-verified missing rows as well as identity exceptions; the 1,398 detail rows therefore avoid double-counting those 20 symbols.

A report defect was found: `range_verification.json` used a nonexistent top-level `missing_count` and consequently reported zero despite nonzero CSV totals. Corrected:
- Commit `c4c6e135bd0cdc4a584b17b2214fb745c2b97acb`: JSON summary now derives missing, identity, expected and verified totals from the coverage DataFrame, and emits issue-type counts from the detail CSV.
- Commit `181423957f28253059c5a41fb792ed7e7f9b917d`: added two tests for aggregate totals and missing-frame behavior.
- Regression on the test commit: **731 passed** (run `43568642666`); Yahoo Adapter **56 passed** (run `43568642668`).
- Corrected range rerun: workflow run `43568626542` on script-fix commit `c4c6e135bd0cdc4a584b17b2214fb745c2b97acb`; last observed IN PROGRESS. Its final JSON/CSV artifact must be inspected before this correction is accepted.

The reconciliation output remains evidence, not automatic authorization to approve any symbol. Unknown MII symbols and ISIN mismatches require source-level resolution.

## 6. Remaining acceptance conditions

1. Recheck completion and artifact for alignment workflow run 43564379235 (180-session service default); the full 83-session artifact 14101766488 has already been reviewed.
2. Resolve or formally accept the official MII publication-time limitation. Until then, strict point-in-time availability remains REVIEW.
3. Investigate the missing-member and identity-exception clusters, especially 2026-08-14, 2026-08-10, 2026-11-02 and 2026-10-29, using authoritative NSE evidence only. Do not lower thresholds or fabricate records.
4. Record the final alignment-run outcome and decide whether the remaining REVIEW gates are acceptable for Chapter 02 acceptance; do not auto-promote REVIEW to PASS.

## 7. Safety gates

- Main branch unchanged; PR #2 remains Draft / Unmerged.
- Chapter 01 acceptance remains separate.
- BSE: DISABLED.
- Sector Mapping Expansion: OFF.
- F&O Scanner: EXCLUDED.
- No fabricated, forward-filled or Yahoo-derived NSE membership observations.
- No merge until the alignment workflow is complete and the point-in-time / universe coverage REVIEW conditions are explicitly resolved or formally accepted.

End of Chapter 02 Acceptance Register.
