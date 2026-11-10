TradeLab Pro — Chapter 25, Step 27

Production Provenance Validation Specification & Test Plan

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 27
Review Date: 2026-11-10
Repository: formarketon-lang/123
Branch: main

1. Objective

Define the production source-authenticity and snapshot-integrity requirements for NSE/BSE exchange-universe reconciliation.

This step documents the required controls and test plan. It does not claim that the controls have already been implemented.

2. Existing Code Review

Files inspected:

- "data/providers/exchange_universe_reconciliation.py"
- "scripts/run_exchange_universe_reconciliation.py"
- "tests/test_exchange_universe_reconciliation.py"

Existing "validate_metadata()" currently checks:

- Required metadata fields.
- Exchange name.
- Non-empty filename.
- HTTPS URL and hostname presence.
- SHA-256 string format.
- Timezone-aware download timestamp.
- Trading date format.

3. Critical Test Gap

The existing test fixture uses:

"https://example.com/security-master.csv"

The current metadata validator accepts HTTPS URLs without verifying whether the hostname belongs to the stated exchange.

Consequently, a syntactically valid metadata record can pass without proving official exchange provenance.

Required correction: Production validation must reject example.com, third-party mirrors and all unapproved hostnames.

Do not weaken existing validation tests to accommodate production source restrictions. Separate test fixtures from production authorization.

4. Proposed Source Policy

Production source validation must use an explicit exchange-to-hostname allowlist.

Initial policy:

Exchange| Official source policy
NSE| Independently verified NSE-controlled hostname
BSE| Independently verified BSE-controlled hostname
Unknown exchange| Reject
Third-party mirror| Reject
example.com test fixture| Reject in production mode

Important:

- Do not invent a direct BSE download hostname.
- Do not assume a member-only source is publicly accessible.
- Record the actual source URL only after verifying the download location.
- Any new hostname must be reviewed before allowlisting.

5. Required Production Validation

A. Source authenticity

- Exact exchange match.
- HTTPS required.
- Approved hostname required.
- Reject hostname lookalikes and unapproved redirects.
- Reject credentials embedded in URLs.
- Reject unknown exchange values.

B. Snapshot integrity

- Original downloaded file must be retained.
- SHA-256 must be calculated from original file bytes.
- Supplied checksum must match the calculated checksum.
- ZIP archive integrity must be checked.
- Expected BSE CSV member must be present exactly once.
- Original filename must be preserved.

C. Timestamp and date

- Download timestamp must be timezone-aware.
- UTC timestamp must be recorded consistently.
- Trading date must be a valid ISO date.
- Missing or malformed metadata must fail closed.

D. Security master structure

- Required columns must exist.
- Empty snapshots must be rejected.
- Duplicate identity records must be reported.
- NSE and BSE must be audited independently.
- Active, suspended and inactive records must not be silently mixed.

6. Required Automated Test Plan

Test| Expected result
Official approved NSE hostname| Accept
Official approved BSE hostname| Accept
example.com hostname| Reject
Third-party mirror hostname| Reject
Hostname lookalike| Reject
HTTP URL| Reject
Unknown exchange| Reject
Missing source URL| Reject
Missing filename| Reject
Invalid SHA-256 format| Reject
Correct format but mismatched file checksum| Reject
Naive timestamp without timezone| Reject
Invalid trading date| Reject
Corrupt ZIP archive| Reject
Missing BSE CSV member| Reject
Multiple matching BSE CSV members| Reject
Missing required security master column| Reject
Empty snapshot| Reject
Valid snapshot with duplicate ISIN| REVIEW
Valid snapshot with missing identity| REVIEW
Sector mapping activation attempt| Remain OFF

7. Test Architecture Requirements

1. Keep pure metadata validation separate from actual file checksum verification.
2. Use temporary local files for checksum tests.
3. Use synthetic fixture data only for automated tests.
4. Do not use test fixtures as real exchange-source evidence.
5. Avoid live exchange downloads in ordinary pytest tests.
6. Add live-source verification as a separate controlled audit.
7. Ensure failure cases return REVIEW or raise a controlled validation error.
8. Preserve existing exchange identity and cross-listing tests.

8. Production Approval Gates

Production reconciliation may be considered only when all of these are true:

- NSE source hostname verified.
- BSE source hostname verified.
- Access authorization verified where required.
- Original dated NSE snapshot retained.
- Original dated BSE snapshot retained.
- Both SHA-256 checksums independently reproduced.
- Production metadata validation passes.
- Real exchange reconciliation passes.
- Generated audit outputs are retained.

A passing synthetic test suite alone is not production approval.

9. Current Decision

EXISTING METADATA VALIDATOR REVIEWED

EXAMPLE.COM FIXTURE GAP IDENTIFIED

PRODUCTION HOSTNAME ALLOWLIST REQUIRED

FILE CHECKSUM VERIFICATION REQUIRED

AUTOMATED TEST PLAN DEFINED

IMPLEMENTATION NOT YET CLAIMED

REAL NSE/BSE RECONCILIATION: NOT APPROVED

SECTOR MAPPING EXPANSION: HOLD

10. Next Step — Chapter 25, Step 28

Implement the reviewed production provenance controls in the existing reconciliation module and extend the existing test file.

Before editing, preserve existing behavior that is already valid. Do not create duplicate reconciliation modules.

Project Checkpoint

"TLP-CP-2026-11-10-PHASE-04-CH25-STEP-27-PROVENANCE-SPEC-TEST-PLAN-HOLD"
