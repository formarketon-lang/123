# TradeLab Pro — Chapter 25, Step 35

## Independent Exchange Checksum Verification Audit

Project: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 35
Repository: formarketon-lang/123
Branch: main

## 1. Objective

Verify whether independently published official NSE/BSE
checksum evidence is available for retained exchange snapshots.

A SHA-256 calculated by the same downloader that created
the snapshot is an integrity fingerprint, not independent
exchange checksum evidence.

## 2. Existing Implementation

Inspected:

- data/providers/exchange_snapshot_downloader.py
- data/providers/exchange_universe_reconciliation.py
- scripts/run_exchange_universe_reconciliation.py
- tests/test_exchange_universe_reconciliation.py

Existing controls:

- SHA-256 calculated from original file bytes.
- Snapshot size verification.
- Optional expected SHA-256 comparison.
- Original snapshot retention.
- Provenance JSON retention.
- NSE source hostname restriction.
- BSE downloader disabled.

## 3. Critical Gap

The current implementation does not establish that an
expected checksum was independently published by the
relevant exchange.

A checksum copied from the downloader's own provenance
file cannot be treated as independent evidence.

An operator-entered hash without verifiable source evidence
must not receive production approval.

## 4. Required Evidence

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

Missing evidence must produce REVIEW.

## 5. NSE Policy

NSE remains the primary exchange.

An official checksum publication must be independently
identified before it can be accepted.

Do not assume that a snapshot's downloader-generated
SHA-256 is an NSE-published checksum.

## 6. BSE Policy

BSE checksum verification remains blocked until:

- Official source is independently verified.
- TLP access authorization is verified.
- Original BSE snapshot is retained.
- Independent checksum evidence is available.

Do not enable BSE downloads in this step.

## 7. Required Tests

- Missing independent checksum evidence returns REVIEW.
- Invalid checksum format is rejected.
- Wrong snapshot filename association is rejected.
- Mismatched independent checksum is rejected.
- Matching independently sourced checksum passes.
- Unapproved checksum source URL is rejected.
- Modified checksum evidence is rejected.
- Downloader-generated hash alone is not independent evidence.
- BSE remains disabled.
- Sector Mapping remains OFF.

## 8. Production Approval Gates

production_checksum_verified = False
independent_checksum_evidence_available = False
bse_production_approved = False
mapping_eligible = False
sector_mapping_activated = False

These values must remain closed until independently
verified evidence and automated tests pass.

## 9. Current Decision

INDEPENDENT CHECKSUM PUBLICATION: NOT YET VERIFIED

EXISTING FILE HASH VERIFICATION: IMPLEMENTED

INDEPENDENT EXCHANGE CHECKSUM: NOT APPROVED

PRODUCTION RECONCILIATION: HOLD

SECTOR MAPPING EXPANSION: OFF

## 10. Next Action

Identify and verify official exchange checksum evidence.
Implement strict independent checksum validation only
after the source and evidence format are established.

Checkpoint:

TLP-CP-2026-11-12-PHASE-04-CH25-STEP-35-INDEPENDENT-CHECKSUM-AUDIT-HOLD
