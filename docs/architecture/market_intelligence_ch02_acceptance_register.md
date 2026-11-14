# TLP-MIM-001 — Chapter 02 Acceptance Register

Project: TLP-MIM-001  
Parent: TLP-MASTER-001  
Repository: formarketon-lang/123  
Branch: ch02-advance-decline-plan  
Base: main  
Chapter: 02 — Historical Advance / Decline Analysis  
Checkpoint: TLP-CP-2026-11-14-TLP-MIM-001-CH02-STEP-11-RANGE-VERIFICATION-IN-PROGRESS  
Register status: TECHNICAL IMPLEMENTATION VERIFIED; FULL RANGE EVIDENCE AND POINT-IN-TIME REVIEW GATE OPEN  
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
| 11 | Final Verification | IN PROGRESS | Regression green; official 120-day calendar PASS; first range artifact covers only 60/83 sessions |

## 2. Latest GitHub Actions verification

Latest PR regression commit: `f494290101c6313c88a5b957de2bf3ca40ebc9e8`.

- TradeLab Pro Tests: **727 passed**, workflow run `43563135790`.
- Yahoo Adapter Unit Tests: **56 passed**, workflow run `43563135837`.
- Both latest PR workflows completed successfully; no failures in these latest runs.
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

## 6. Remaining acceptance conditions

1. Review the new 83-session range artifact. The previous 60-session artifact is not complete coverage of the 120-calendar-day period.
2. Resolve or formally accept the official MII publication-time limitation. Until then, strict point-in-time availability remains REVIEW.
3. Review whether missing members and identity exceptions can be authoritatively reconciled from NSE evidence. Do not lower validation thresholds or fabricate records to force PASS.
4. Update this register and checkpoint with the final full-range artifact and latest regression run IDs.

## 7. Safety gates

- Main branch unchanged; PR #2 remains Draft / Unmerged.
- Chapter 01 acceptance remains separate.
- BSE: DISABLED.
- Sector Mapping Expansion: OFF.
- F&O Scanner: EXCLUDED.
- No fabricated, forward-filled or Yahoo-derived NSE membership observations.
- No merge until the full-range artifact and acceptance conditions are reviewed.

End of Chapter 02 Acceptance Register.
