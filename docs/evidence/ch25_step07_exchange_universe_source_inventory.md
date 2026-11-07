TradeLab Pro — Chapter 25, Step 07

Official NSE and BSE Exchange Universe Source Inventory

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 07
Review date: 2026-11-07
Decision: PARTIAL SOURCE IDENTIFICATION — HOLD

1. Objective

Identify separate authoritative reference-universe sources for NSE and BSE cash-equity securities before full-universe classification reconciliation.

No company classification or exchange membership may be inferred.

2. NSE Official Sources

Source A — NSE All Reports

URL: https://www.nseindia.com/all-reports

Relevant report:

- CM - MII - Security File (NSE Listed securities)
- CM - MII - Security File (NSE Listed and BSE Exclusive securities)

Source B — NSE Securities Available for Trading

URL: https://www.nseindia.com/static/market-data/securities-available-for-trading

Relevant report:

- Securities available for Equity segment (.csv)

Existing TLP implementation:

- "scripts/run_nse_universe_live_check.py"
- "scripts/run_nse_eq_coverage_audit.py"
- "data/providers/nse_universe.py"

Status: OFFICIAL SOURCE DISCOVERY VERIFIED — ACTUAL SNAPSHOT AND DATE-SPECIFIC COVERAGE RECONCILIATION REQUIRED.

Important: The combined NSE MII file includes NSE-listed and BSE-exclusive records. It must not be treated as an NSE-only or BSE-only universe without applying and verifying the correct exchange scope.

3. BSE Official Source

Required reference:

- BSE-listed cash-equity securities.
- Official exchange source URL.
- Downloadable security master or equivalent authoritative list.
- Download timestamp and applicable trading date.
- Security code, company name, ISIN and security type where available.

Current status: NOT VERIFIED.

No third-party substitute or NSE combined file is accepted as proof of the complete BSE universe.

4. Mandatory Snapshot Metadata

For every exchange snapshot, retain:

- Exchange name
- Original source URL
- Original filename
- Download timestamp in UTC
- Applicable trading date
- Original file checksum (SHA-256)
- Record count
- Column names
- Security eligibility rules
- Excluded-record count and reasons

5. Reconciliation Rules

1. Keep NSE and BSE universes separate.
2. Use ISIN as the primary identity key where available.
3. Validate exchange symbol and security code separately.
4. Detect duplicate ISINs and identity conflicts.
5. Document SME, suspended, delisted and other exclusions explicitly.
6. Do not treat index constituents as a complete exchange universe.
7. Do not infer sector classification from company names or symbols.

6. Current Evidence Matrix

Requirement| Status
NSE official MII source identified| VERIFIED
NSE Equity CSV source identified| VERIFIED
Existing NSE audit scripts inspected| VERIFIED
NSE dated snapshot retained in this step| PENDING
BSE official complete universe source| NOT VERIFIED
BSE dated snapshot retained| NOT STARTED
NSE/BSE separate reconciliation| NOT STARTED

7. Production Controls

nse_universe_source_verified = True
nse_snapshot_reconciled = False

bse_universe_source_verified = False
bse_snapshot_reconciled = False

full_nse_bse_universe_verified = False
mapping_eligible = False
sector_mapping_activated = False

8. Next Actions

1. Retain a dated official NSE MII snapshot and its checksum.
2. Verify NSE EQ eligibility and reconcile the saved snapshot.
3. Identify and verify the official BSE cash-equity security master.
4. Retain a separate BSE snapshot and checksum.
5. Reconcile each exchange independently.
6. Proceed to classification coverage only after both reference universes are established.

9. Final Decision

PARTIAL SOURCE IDENTIFICATION — HOLD.

NSE official universe sources and existing audit tooling have been identified. Complete BSE reference-universe evidence remains outstanding.

Sector Mapping must remain OFF.

Project Checkpoint:
"TLP-CP-2026-11-07-CH25-STEP-07-EXCHANGE-UNIVERSE-SOURCE-INVENTORY-HOLD"
