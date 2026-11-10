TradeLab Pro — Chapter 25, Step 26

Official BSE Security Master Source & Provenance Review

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 26
Review Date: 2026-11-10
Repository: formarketon-lang/123
Branch: main

1. Objective

Verify the official BSE Equity Security Master source using BSE-published documentation and define production provenance controls.

This review does not approve a production BSE universe or activate Sector Mapping.

2. Official BSE Source Evidence

Evidence A — BSE Equity Segment Master Circular (2025)

https://www.bseindia.com/markets/MarketInfo/DownloadAttach.aspx?attachedId=8a7fec3a-95bc-4bd2-82de-76e2a84e2915&id=20250429-51

The circular confirms:

- BSE provides end-of-day master data files.
- Master files are available through the BSE Member Extranet and Members Help Desk.
- The official Extranet URL is https://member.bseindia.com.
- The circular identifies the BSE website Members Help Desk as another access route.

Relevant section: 5.6 Extranet facility and 5.7 Master Data Files.

Evidence B — Standardised Security Master File Format

https://www.bseindia.com/markets/MarketInfo/DownloadAttach.aspx?attachedId=e99e2ca5-95d7-4173-83da-7774412bbb2d&id=20220531-44

BSE specifies the file:

"BSE_EQ_SCRIP_DDMMYYYY.csv"

The documented fields include:

- Scrip Code
- Instrument Code / Security Symbol
- Group Name
- Scrip Name
- ISIN Code
- Security Type Flag
- Instrument Status Flag
- Instrument Type

The documented status values include Active (A), Suspend (S), and Inactive (I).

The documented instrument type includes E for Equity trading.

3. BSE Source Verification Decision

Requirement| Result
BSE-published master circular located| VERIFIED
Official BSE master-file access route documented| VERIFIED
Official BSE file naming convention documented| VERIFIED
Scrip Code, Symbol and ISIN fields documented| VERIFIED
Active, suspended and inactive status fields documented| VERIFIED
Direct public automated download URL verified| PENDING
TLP access permission confirmed| PENDING
Actual dated BSE ZIP snapshot retained| PENDING
Original snapshot SHA-256 recorded| PENDING
Real BSE reconciliation executed| NOT RUN

Important: Official documentation establishes the source and file format. It does not establish that TLP currently has unrestricted automated access or permission to redistribute the data.

4. Existing TLP Implementation Review

Existing implementation is retained:

- "data/providers/exchange_universe_reconciliation.py"
- "scripts/run_exchange_universe_reconciliation.py"
- "tests/test_exchange_universe_reconciliation.py"

The existing BSE loader expects a ZIP archive containing exactly one "BSE_EQ_SCRIP*.csv" file.

It currently filters:

- "FinInstrmTp = E"
- "SctyTpFlg = EQ"
- "Sts = A"

This is an active-equity selection rule, not a complete historical or suspended-security universe.

No duplicate loader or reconciliation module is required at this step.

5. Production Provenance Controls Required

The existing metadata validator checks HTTPS, but HTTPS alone does not prove official source authenticity.

Before production use, implement and test:

1. Exchange-specific hostname allowlisting.
2. Exact source URL and original filename retention.
3. UTC download timestamp and applicable trading date.
4. SHA-256 verification against original downloaded bytes.
5. ZIP integrity and expected CSV member validation.
6. Required column and schema validation.
7. Explicit active, suspended and inactive status accounting.
8. Rejection of test fixture domains in production mode.
9. Rejection of missing or invalid source metadata.
10. Retention of original snapshots and audit outputs.

Do not accept third-party mirrors as official BSE provenance.

6. Recommended Source Policy

BSE source discovery is accepted based on BSE-published documentation.

The actual production download route must be recorded only after the file has been retrieved from an independently verified BSE-controlled location.

Do not invent or assume a permanent direct download URL.

If access requires member authentication, record that restriction and obtain the appropriate access authorization before automation.

7. Safety Gate

bse_official_master_documentation_verified = True
bse_master_file_format_verified = True

bse_direct_download_url_verified = False
bse_access_permission_verified = False
bse_dated_snapshot_retained = False
bse_snapshot_sha256_verified = False

production_source_allowlist_verified = False
real_bse_reconciliation_passed = False
complete_nse_bse_universe_verified = False

mapping_eligible = False
sector_mapping_activated = False

8. Step 26 Result

OFFICIAL BSE SECURITY MASTER DOCUMENTATION VERIFIED

OFFICIAL FILE FORMAT AND IDENTITY FIELDS VERIFIED

DIRECT AUTOMATED DOWNLOAD AND ACCESS PERMISSION PENDING

REAL BSE SNAPSHOT AND CHECKSUM PENDING

PRODUCTION PROVENANCE CONTROLS STILL REQUIRED

FULL NSE/BSE UNIVERSE: HOLD

SECTOR MAPPING EXPANSION: HOLD

9. Next Step — Chapter 25, Step 27

Prepare the production provenance validation specification and test plan.

Reuse the existing reconciliation module. Do not approve real BSE data until source access, original snapshot, checksum and source-domain validation are independently verified.

Project Checkpoint

"TLP-CP-2026-11-10-PHASE-04-CH25-STEP-26-BSE-SOURCE-VERIFIED-PROVENANCE-HOLD"
