TradeLab Pro — Chapter 25, Step 25

Official NSE/BSE Universe Reconciliation Readiness Audit

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 25
Review Date: 2026-11-10
Repository: formarketon-lang/123
Branch: main

1. Objective

Review the existing NSE/BSE exchange-universe reconciliation implementation and identify the remaining evidence required for a real, dated exchange-wise reconciliation.

No production universe approval is granted by this review.

2. Official NSE Sources Identified

NSE All Reports:
https://www.nseindia.com/all-reports

NSE Securities Available for Trading:
https://www.nseindia.com/static/market-data/securities-available-for-trading

Identified official reports include:

- Securities available for Equity segment.
- Securities available for trading in SME.
- CM MII Security File — NSE listed securities.
- CM MII Security File — NSE listed and BSE-exclusive securities.

Important source-scope control:

The combined MII file must not be treated as an NSE-only or BSE-only universe without applying and verifying exchange scope.

The official securities-available page lists Equity and SME datasets separately.

3. NSE Classification Source

Official NSE Industry Classification:
https://www.nseindia.com/static/products-services/industry-classification

The four taxonomy levels are:

1. Macro Economic Sector
2. Sector
3. Industry
4. Basic Industry

This taxonomy is not a substitute for the exchange security master.

Exchange identity and classification membership must remain separate datasets.

4. Existing Repository Implementation

Existing files found:

- "data/providers/exchange_universe_reconciliation.py"
- "scripts/run_exchange_universe_reconciliation.py"
- "data/providers/nse_universe.py"
- "data/universe.py"
- "tests/test_exchange_universe_reconciliation.py"
- "scripts/run_nse_universe_live_check.py"

The reconciliation implementation already supports:

- Separate NSE and BSE input snapshots.
- NSE EQ-series filtering.
- BSE active equity filtering.
- Symbol, ISIN and company identity checks.
- Duplicate symbol and duplicate ISIN detection.
- Cross-listed ISIN reporting.
- Snapshot SHA-256 calculation.
- Source URL and download timestamp metadata.
- Explicit separation of identity reconciliation from sector classification.

Existing implementation is reused. No duplicate implementation is proposed.

5. Existing Test Coverage

Repository tests include:

- Separate exchange universe checks.
- Cross-listed ISIN detection.
- Duplicate NSE ISIN detection.
- Duplicate BSE symbol detection.
- Invalid ISIN rejection.
- Missing company identity rejection.
- Invalid source metadata rejection.
- NSE EQ-series filtering.
- BSE active EQ filtering.
- NSE MII diagnostic filtering.
- Sector mapping must remain inactive.

These are code-level test fixtures. They do not prove that real exchange snapshots have passed reconciliation.

6. Important Provenance Review Finding

The current metadata validator checks that the source URL is HTTPS, but does not independently establish that the domain is an authorized official exchange source.

Therefore:

- A syntactically valid HTTPS URL is not proof of official provenance.
- Production source-domain allowlisting or an independently reviewed source authorization check is still required.
- Test fixture URLs must never be accepted as production evidence.
- Actual file checksums must be calculated from original downloaded snapshots.

This must be addressed before production approval.

7. Current Evidence Matrix

Requirement| Status
Official NSE Equity source identified| VERIFIED
Official NSE SME source identified| VERIFIED
Official NSE MII source identified| VERIFIED
Combined MII scope limitation documented| VERIFIED
Existing reconciliation code found| VERIFIED
Existing reconciliation tests found| VERIFIED
Dated NSE snapshot retained for this step| NOT SUPPLIED
Official BSE source independently verified| PENDING
Dated BSE snapshot retained| NOT SUPPLIED
Real NSE reconciliation executed| NOT RUN
Real BSE reconciliation executed| NOT RUN
Cross-exchange reconciliation executed| NOT RUN
Production provenance allowlist| NOT VERIFIED
Complete NSE/BSE universe approved| NOT APPROVED

8. Required Next Actions

1. Obtain the official NSE Equity and SME snapshots with download timestamps.
2. Identify and verify the official BSE cash-equity security-master source.
3. Obtain a dated BSE snapshot.
4. Retain original filenames and SHA-256 checksums.
5. Run the existing reconciliation script with actual snapshots.
6. Review missing identity, duplicate and cross-listed ISIN results.
7. Verify source-domain authorization and metadata.
8. Retain generated detail CSV and summary JSON as audit evidence.
9. Run automated tests and GitHub Actions.
10. Keep sector classification outside the exchange identity reconciliation.

9. Production Safety Gate

nse_official_source_identified = True
nse_dated_snapshot_verified = False

bse_official_source_verified = False
bse_dated_snapshot_verified = False

real_exchange_reconciliation_passed = False
source_domain_provenance_verified = False

complete_exchange_universe_verified = False
mapping_eligible = False
sector_mapping_activated = False

10. Step 25 Result

EXISTING RECONCILIATION IMPLEMENTATION FOUND

OFFICIAL NSE EQUITY AND SME SOURCES IDENTIFIED

BSE OFFICIAL SOURCE EVIDENCE STILL PENDING

NO REAL DATED SNAPSHOT RECONCILIATION EXECUTED

PROVENANCE VALIDATION NEEDS HARDENING

FULL NSE/BSE UNIVERSE: HOLD

SECTOR MAPPING EXPANSION: HOLD

11. Next Step

Chapter 25 — Step 26

Resolve official BSE source verification and production provenance controls.

Reuse the existing reconciliation implementation. Do not create duplicate modules.

Project Checkpoint

TLP-CP-2026-11-10-PHASE-04-CH25-STEP-25-EXCHANGE-UNIVERSE-READINESS-HOLD
