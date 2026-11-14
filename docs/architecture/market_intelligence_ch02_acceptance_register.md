# TLP-MIM-001 — Chapter 02 Acceptance Register

Project: TLP-MIM-001  
Parent: TLP-MASTER-001  
Repository: formarketon-lang/123  
Branch: ch02-advance-decline-plan  
Base: main  
Chapter: 02 — Historical Advance / Decline Analysis  
Checkpoint: TLP-CP-2026-11-14-TLP-MIM-001-CH02-STEP-11-VERIFIED-REVIEW-CONDITIONS  
Register status: STEP 11 TECHNICAL VERIFICATION PASS; CHAPTER ACCEPTANCE HELD FOR EVIDENCE GAPS  
PR: #2 — Draft / Unmerged

---

## 1. Step acceptance

| Step | Scope | Status | Verification |
|---|---|---|---|
| 01 | Existing architecture inventory | PASS | Existing NSE UDiFF/MII/breadth path inspected; no duplicate downloader |
| 02 | Point-in-time NSE CM/EQ universe contract | CONTRACT DOCUMENTED; AUTOMATED ACCEPTANCE OPEN | 12-scenario contract matrix documented; not 12 automated tests |
| 03 | Historical observation retrieval | PASS | Existing single-date NSE service orchestrated per requested date |
| 04 | Prior-session validation | PASS | Existing verified-calendar contract and focused tests |
| 05 | Daily A/D classification | PASS | Reuses existing breadth classifier; missing != unchanged |
| 06 | A-D Difference / A-D Ratio | PASS | 17 focused cases; zero-denominator state explicit |
| 07 | Cumulative A-D Line | PASS | 15 focused cases; non-PASS sessions break segments |
| 08 | Pure Core Analysis | PASS | 12 focused cases; provenance, coverage and status composition |
| 09 | Historical A/D Service | PASS | 10 focused cases; existing retriever reused |
| 10 | Market Intelligence UI | PASS | 4 focused UI tests; TradeLab Pro run #531 previously 712 passed |
| 11 | Final Verification | PASS WITH LIVE REVIEW CONDITION | Live NSE smoke test and latest regression verified; see evidence below |

## 2. Latest automated verification

- Latest full TradeLab Pro regression: **714 passed**.
- Latest Yahoo Adapter regression: **56 passed**.
- Latest regression commit: `e3c9ecc3e0031e96e33a2b95ea08122cb3f182a4`.
- Historical A/D live workflow: PASS as a verification workflow; run `43561818820`.
- Live evidence artifact: `tlp-mim-ch02-historical-ad-live-evidence`; artifact SHA-256 `dcaf9504a62183e8d0c2f62918697a8d594946cca33033e7c9a977c0d0867d52`.
- The workflow's successful exit does not mean the NSE dataset passed full-universe validation. The actual observation status is REVIEW.

## 3. Live NSE evidence — 2026-11-13

Official NSE CM Bhavcopy:
- Source: NSE
- File: `BhavCopy_NSE_CM_0_0_0_20261113_F_0000.csv.zip`
- URL: https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_20261113_F_0000.csv.zip
- Archive SHA-256: `758ec3b60fd492a29ff3ebc6c069269bc326dc5ca662cfba8892f16939841b7b`
- Fetched at UTC: `2026-11-14T05:30:35.075915Z`
- Dated MII snapshot: `2026-11-13`

Reconciliation:
- Expected NSE CM/EQ members: **2,762**
- Verified observations: **2,742**
- Missing expected members: **20**
- Identity exceptions: **2**
- Coverage: **99.2759%**
- Daily verified-subset classification: Advancing **938**, Declining **1,776**, Unchanged **28**
- A-D Difference: **-838**
- A/D Ratio: **0.5281531532**
- Daily status: **REVIEW**
- Cumulative A-D value: **not emitted** for this REVIEW session.

Reconciliation checks:
- 938 + 1,776 + 28 = 2,742 verified observations.
- 2,742 + 20 missing = 2,762 expected universe members.
- 2,742 / 2,762 × 100 = 99.2759% (rounded to the official four-decimal coverage precision).
- A-D Difference = 938 − 1,776 = -838.
- A/D Ratio = 938 / 1,776 = 0.5281531532.

Interpretation:
- These daily counts describe only the 2,742 verified observations, not the complete NSE CM/EQ universe.
- The 20 missing rows and 2 identity exceptions correctly retain REVIEW.
- The cumulative A-D series does not bridge or calculate through this REVIEW date.
- No Yahoo membership substitution, forward-fill or fabricated observation was used.

## 4. Open evidence / acceptance conditions

1. Official NSE trading-session calendar retrieval/authentication is not implemented. Callers must provide independently verified NSE sessions; the UI does not infer weekdays or holidays.
2. Historical validation is currently a one-session live smoke test. Multi-month historical-range live verification remains pending.
3. Raw dated MII archive SHA-256 and actual fetch timestamp are not yet exposed in the production historical service result. Bhavcopy raw archive provenance is present; MII raw archive provenance remains an evidence gap.
4. The 12 Step 02 scenarios are documented contract cases, not a completed automated test suite.
5. Live 2026-11-13 coverage is REVIEW (99.2759%); no full-universe PASS claim is permitted.

Chapter 02 must not be described as fully accepted until the required point-in-time universe evidence, calendar integration/verification approach, and historical-range evidence are closed or explicitly approved as review conditions by the project owner.

## 5. Safety gates

- Main branch unchanged; PR #2 remains Draft / Unmerged.
- Chapter 01 acceptance remains separate.
- BSE: DISABLED.
- Sector Mapping Expansion: OFF.
- F&O Scanner: EXCLUDED.
- No fabricated, forward-filled or Yahoo-derived NSE membership observations.

End of Chapter 02 Acceptance Register.
