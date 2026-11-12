# TradeLab Pro — Chapter 25, Step 35

## Independent Exchange Checksum Verification Audit

Project: TLP-MASTER-001  
Part: 04  
Chapter: 25  
Step: 35  
Repository: formarketon-lang/123  
Branch: main  
Review Date: 2026-11-12

## 1. Objective

Verify whether independently published official NSE/BSE
checksum evidence is available for retained exchange snapshots.

A SHA-256 calculated by the same downloader that created
the snapshot is an integrity fingerprint, not independent
exchange checksum evidence.

## 2. Existing Implementation

Reviewed components:

- data/providers/exchange_snapshot_downloader.py
- data/providers/exchange_universe_reconciliation.py
- scripts/run_exchange_universe_reconciliation.py
- tests/test_exchange_universe_reconciliation.py

Existing controls include:

- SHA-256 calculation from original file bytes.
- Snapshot size verification.
- Optional expected SHA-256 comparison.
- Original snapshot retention.
- Provenance JSON retention.
- NSE source hostname restriction.
- BSE downloader disabled.

## 3. NSE Official Source Research

Official NSE reports:

https://www.nseindia.com/all-reports

Official NSE securities available for trading:

https://www.nseindia.com/static/market-data/securities-available-for-trading

Official NSE industry classification:

https://www.nseindia.com/static/products-services/industry-classification

NSE CM MII Security File publication is documented
in the official NSE circular:

https://nsearchives.nseindia.com/content/circulars/MSD60315.pdf

Findings:

- Official NSE security-file publication identified.
- NSE security identity source remains separate from
  sector classification evidence.
- An independently published SHA-256 checksum manifest
  has not been established by this review.

NSE independent checksum status: NOT VERIFIED

## 4. BSE Official Source Research

Official BSE Security Master Format:

https://www.bseindia.com/markets/MarketInfo/DownloadAttach.aspx?attachedId=e99e2ca5-95d7-4173-83da-7774412bbb2d&id=20220531-44

Findings:

- Official BSE Security Master format documented.
- Scrip Code, Symbol and ISIN fields documented.
- Security status fields documented.
- Independent BSE-published checksum manifest
  has not been established by this review.
- Automated download permission remains unverified.

BSE independent checksum status: NOT VERIFIED

## 5. Critical Integrity Distinction

Three different checks must remain separate:

1. Local SHA-256:
   Calculated from retained original snapshot bytes.

2. Expected checksum comparison:
   Compares a supplied expected hash against the
   locally calculated hash.

3. Independent exchange checksum:
   Requires an authenticated exchange-published
   checksum or manifest.

A local SHA-256 alone cannot establish item 3.

## 6. Free-Only Development Policy

TradeLab Pro will prioritize free and officially
accessible exchange sources.

Rules:

- No mandatory paid API dependency.
- No paid vendor data required for basic development.
- NSE remains the primary source.
- Yahoo remains secondary for price-data checks only.
- Official BSE documentation and authorized free
  sources may be used where available.
- No access restriction will be bypassed.
- No unsupported source will be treated as official.
- Missing evidence must produce REVIEW.
- No fake or inferred checksum evidence is permitted.

Paid vendor integration may be considered separately
in the future, but it is not a requirement for this step.

## 7. Required Evidence

For each exchange independently:

- Official checksum publication source.
- Exact source URL.
- Original checksum document or manifest.
- Retrieval timestamp in UTC.
- Original checksum document SHA-256.
- Snapshot filename association.
- Expected snapshot SHA-256.
- Actual retained snapshot SHA-256.
- Verification result.

Missing independent evidence must produce REVIEW.

## 8. Required Tests

- Missing independent checksum evidence returns REVIEW.
- Invalid checksum format is rejected.
- Wrong snapshot filename association is rejected.
- Mismatched independent checksum is rejected.
- Matching independently sourced checksum passes.
- Unapproved checksum source URL is rejected.
- Modified checksum evidence is rejected.
- Downloader-generated hash alone is not independent.
- BSE downloader remains disabled.
- Sector Mapping remains OFF.

## 9. Production Approval Gates

production_checksum_verified = False

independent_checksum_evidence_available = False

bse_production_approved = False

mapping_eligible = False

sector_mapping_activated = False

These values must remain closed until the required
evidence and tests pass.

## 10. Current Decision

NSE OFFICIAL FILE PUBLICATION: IDENTIFIED

BSE OFFICIAL SECURITY MASTER FORMAT: IDENTIFIED

NSE INDEPENDENT CHECKSUM: NOT VERIFIED

BSE INDEPENDENT CHECKSUM: NOT VERIFIED

LOCAL SHA-256 INTEGRITY: IMPLEMENTED

INDEPENDENT EXCHANGE CHECKSUM: HOLD

PRODUCTION RECONCILIATION: HOLD

SECTOR MAPPING EXPANSION: OFF

## 11. Next Action

1. Seek written confirmation from NSE about any
   independently published checksum or signed manifest.

2. Seek equivalent confirmation from BSE.

3. Use free official sources wherever access is
   authorized and available.

4. Implement independent checksum validation only
   after the official evidence format is established.

5. Do not block basic development on paid vendor APIs.

## Project Checkpoint

TLP-CP-2026-11-12-PHASE-04-CH25-STEP-35-OFFICIAL-CHECKSUM-RESEARCH-HOLD
