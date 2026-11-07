TLP Full-Universe Classification Coverage Verification Protocol

Project: TradeLab Pro
Part: 04
Chapter: 25
Workstream: Source Authorization & Data Coverage
Status: PREPARED — AWAITING GITHUB COMMIT AND VALIDATION

1. Objective

Establish a reproducible verification process for company-level industry classification data before enabling sector mapping in TradeLab Pro.

The protocol applies to NSE and BSE cash-equity securities only. It does not authorize any data source or classification mapping.

2. Required Universe

Maintain separate reference universes for:

- NSE Cash Market equity securities
- BSE Cash Market equity securities

The reference universe must be obtained from documented, authoritative exchange sources.

Record the source filename, download timestamp, exchange, applicable trading date, and source URL for every universe snapshot.

Do not assume that one exchange's security list represents the other exchange's complete universe.

3. Mandatory Company-Level Fields

Each classification record must be evaluated for:

Field| Requirement
Exchange| NSE / BSE
Symbol| Exchange-listed symbol
Company Name| Company identity
ISIN| Security identity
Macro Economic Sector| Name and code
Sector| Name and code
Industry| Name and code
Basic Industry| Name and code
Effective Date| Classification validity date
Source Reference| Original source or record reference
Retrieved At| Retrieval timestamp
Provider| Data provider identity

A missing mandatory field must be reported. Do not silently fill missing classifications using assumptions.

4. Coverage Verification

For each exchange, calculate:

- Total eligible securities in the reference universe
- Total securities returned by the provider
- Matched securities by ISIN
- Unmatched reference securities
- Provider-only securities
- Duplicate ISIN records
- Missing Symbol or ISIN
- Missing classification levels
- Conflicting classifications

Acceptance rule: 100% of the defined eligible reference universe must be accounted for.

Any exclusions, including SME or suspended securities, must be explicitly documented with a reason. An unexplained omission is a failure.

5. Identity and Consistency Tests

1. Match securities primarily by ISIN.
2. Validate exchange symbol separately.
3. Detect duplicate ISIN records and conflicting exchange symbols.
4. Detect one symbol associated with multiple ISINs across different dates.
5. Check company-name inconsistencies.
6. Keep NSE and BSE records distinguishable.
7. Never infer an ISIN or sector from a company name alone.

6. Classification Integrity Tests

For every returned record:

- Validate all four classification levels.
- Verify that each code corresponds to its stated classification name.
- Check parent-child hierarchy consistency.
- Check effective dates and classification revisions.
- Identify records with missing or conflicting hierarchy levels.
- Preserve original provider values for audit purposes.

A valid taxonomy structure does not automatically prove that a company's assignment is correct.

7. Provenance and Authorization Tests

The provider must supply written clarification of:

- Original classification source
- Official exchange or authorized-source relationship
- Data collection and update process
- Record-level provenance
- Historical revision handling
- NSE and BSE coverage
- API or dataset access entitlement
- Commercial use permission
- User-facing display permission
- Redistribution and derived-data restrictions

A sample API response or field schema is not sufficient evidence of complete coverage or licensing authorization.

8. Test Dataset

Use MARICO as an initial identity and classification test case:

- Symbol: MARICO
- ISIN: INE196A01026

Also test a representative sample from different sectors and both exchanges when the required evidence is available.

A sample test cannot replace full-universe validation.

9. Final Acceptance Criteria

A source may be considered eligible for further production approval only when all conditions below pass:

1. Complete defined NSE universe coverage.
2. Complete defined BSE universe coverage, if BSE support is claimed.
3. ISIN-based identity reconciliation.
4. All mandatory classification fields validated.
5. Classification hierarchy and effective dates validated.
6. Record-level provenance documented.
7. Written commercial-use authorization obtained where required.
8. Display and redistribution permissions clarified.
9. Historical update and revision behavior tested.
10. Evidence retained in the repository.

Any failed or unverified condition means the source remains on HOLD.

10. Current Control State

source_authenticity_status = "UNVERIFIED"
source_authenticity_verified = False
source_authorized_for_nse_mapping = False
commercial_use_authorized = False
redistribution_authorized = False
mapping_eligible = False
sector_mapping_activated = False

11. Evidence to Retain

Store the following under "docs/evidence/":

- Exchange universe snapshots and source references
- Provider sample responses
- Coverage reconciliation reports
- Missing and duplicate record reports
- Classification hierarchy validation reports
- Written vendor and exchange responses
- Licensing and authorization documents
- Final source approval decision

Do not store API secrets or credentials in the evidence repository.

12. Current Decision

HOLD — NO PRODUCTION MAPPING AUTHORIZATION

GFDL Ticket #39451 has received an acknowledgement, but its substantive technical and licensing response remains pending. The NSE company-level data request also remains pending.

This protocol defines how future evidence will be tested. It does not certify any provider, dataset, or classification assignment.

Checkpoint: "TLP-CP-2026-11-07-PHASE-04-CH25-FULL-UNIVERSE-COVERAGE-PROTOCOL-PREPARED"