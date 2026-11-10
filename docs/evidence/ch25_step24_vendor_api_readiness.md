TradeLab Pro — Chapter 25, Step 24

Vendor API Readiness and Data Validation Gate

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 24
Review Date: 2026-11-10
Repository: formarketon-lang/123
Branch: main

1. Objective

Review the published GlobalDataFeeds Sectoral Classification API documentation and define the technical validation requirements before any production integration.

This is a documentation-readiness review, not production API approval.

2. Documentation Reviewed

Provider: Global Financial Datafeeds LLP

API: "GetSectoralClassification"

Documentation:
https://docs.globaldatafeeds.in/getsectoralclassification-15575605e0

Related documentation:
https://docs.globaldatafeeds.in/type-of-corporate-data-available

3. Documented API Request

Endpoint documented:

"https://test.lisuns.com:4532/GetSectoralClassification"

Documented request parameters:

- "accessKey"
- "exchange"
- "instrumentIdentifiers"
- "sector"
- "industry"
- "basicIndustry"
- "from"
- "to"
- "dTFormat"
- "format"

Important documented limit:

- Maximum 25 instruments per request using "instrumentIdentifiers".

Supported output formats:

- JSON
- XML
- CSV
- CSV Content

Date format options:

- Epoch
- String

The endpoint shown in public documentation is a test endpoint. Production endpoint access has not been independently established.

4. Documented Response Fields

Data Level| Field| Code Field
Macro Economic Sector| MacroEconomicIndicator| MeiCode
Sector| Sector| SectCode
Industry| Industry| IndustryCode
Basic Industry| BasicIndustry| BasicIndustryCode

Additional documented identity and audit fields:

- Symbol
- ScripCode
- CompanyName
- ISIN
- AllotedFrom
- ReceivedAt
- SavedAt

The documentation provides a sample response for TCS. This is a documentation example only and is not accepted as a verified production record.

5. Update and History Information

The provider's corporate-data availability page lists:

- Sectoral Classification update frequency: EOD
- History availability: 30 Days

This is a published provider-level statement.

It does not establish:

- Complete historical classification coverage.
- Historical changes for every security.
- Availability of records before the stated period.
- Complete effective-date history.
- Record-level exchange provenance.

Written clarification is still required.

6. Technical Readiness Matrix

Requirement| Status
Public API documentation| VERIFIED
API request parameters documented| VERIFIED
Four taxonomy levels documented| VERIFIED
Four taxonomy code fields documented| VERIFIED
Symbol and ISIN fields documented| VERIFIED
Date and audit fields documented| VERIFIED
Request limit documented| VERIFIED
Output formats documented| VERIFIED
EOD update frequency stated| PROVIDER DOCUMENTED
30-day history stated| PROVIDER DOCUMENTED
Production endpoint confirmed| NOT VERIFIED
Valid API credentials received| NOT VERIFIED
Live API request tested| NOT TESTED
MARICO production sample received| NOT SUPPLIED
Complete NSE/BSE universe tested| NOT TESTED
Record-level source provenance| NOT VERIFIED

7. Mandatory Validation Plan

When authorized API access and credentials are supplied:

1. Test authentication without exposing the access key.
2. Test NSE and BSE separately.
3. Validate the documented response structure.
4. Check Symbol, ScripCode and ISIN consistency.
5. Validate all four taxonomy levels and code fields.
6. Check missing, null and duplicate records.
7. Validate effective-date and received/saved timestamps.
8. Request MARICO using ISIN "INE196A01026".
9. Compare supplied records against official NSE identity and taxonomy evidence.
10. Reconcile coverage against the official NSE and BSE cash-equity universes.
11. Record API errors, missing records and differences.
12. Run automated tests and GitHub Actions.

No real credentials or production data have been tested in this step.

8. Security Controls

- Never commit API keys or passwords.
- Never place credentials in public source files.
- Use protected environment secrets for future authorized integration.
- Do not log access keys in application logs.
- Do not use test sample data as production classification data.

9. Production Approval Gate

api_documentation_verified = True
api_request_schema_documented = True
four_level_taxonomy_documented = True

production_endpoint_verified = False
api_credentials_received = False
live_api_test_passed = False
marico_sample_verified = False
complete_universe_verified = False
record_level_provenance_verified = False

commercial_use_authorized = False
redistribution_authorized = False

mapping_eligible = False
sector_mapping_activated = False

10. Step 24 Result

PUBLIC API DOCUMENTATION REVIEWED

REQUEST AND RESPONSE SCHEMA DOCUMENTED

FOUR-LEVEL TAXONOMY FIELDS IDENTIFIED

EOD AND 30-DAY HISTORY STATEMENTS RECORDED

PRODUCTION API NOT TESTED

COMPLETE COVERAGE NOT VERIFIED

COMMERCIAL LICENSING NOT APPROVED

SECTOR MAPPING EXPANSION: HOLD

11. Next Step

Chapter 25 — Step 25

Proceed with the next available official-source and vendor-evidence validation work.

Do not activate Sector Mapping Expansion until all technical, source-authenticity, coverage and licensing requirements are independently satisfied.

Project Checkpoint

"TLP-CP-2026-11-10-PHASE-04-CH25-STEP-24-API-READINESS-REVIEW-HOLD"
