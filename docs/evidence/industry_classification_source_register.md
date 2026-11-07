TradeLab Pro — Independent Source Authenticity Verification

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 21
Status: REVIEW COMPLETE — HOLD
Date: 2026-11-07

1. Objective

Verify the authenticity, ownership, company-level coverage and commercial authorization of candidate industry-classification sources.

2. NSE Official Classification

Official source:
https://www.nseindia.com/static/products-services/industry-classification

Findings:

- NSE Indices Ltd. owns the classification framework.
- Four-tier taxonomy: Macro Economic Sector, Sector, Industry and Basic Industry.
- Classification methodology uses company business activity and revenue.

Result: Official taxonomy verified.

Limitation: Complete downloadable company-level Symbol and ISIN mapping is not established.

3. GFDL API Assessment

Provider: Global Financial Datafeeds LLP

API documentation:
https://docs.globaldatafeeds.in/getsectoralclassification-15575605e0

Documented fields:

- Symbol
- ScripCode
- CompanyName
- ISIN
- MacroEconomicIndicator
- Sector
- Industry
- BasicIndustry
- AllotedFrom

Result: Required field structure documented.

However:

- Complete NSE/BSE universe coverage is not verified.
- Record-level official provenance is not independently authenticated.
- Live production API data has not been validated.
- Commercial authorization is not established.

Support Ticket: 39451

Acknowledgement recorded: 2026-11-07.
Substantive response pending.

4. Commercial Licensing

Provider purchase conditions:
https://globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/pricing-sales/who-can-purchase/

Provider terms:
https://globaldatafeeds.in/terms-and-conditions/

Findings:

- Public API purchase conditions specify personal-use restrictions.
- Commercial use requires applicable exchange agreements and fees.
- Redistribution requires explicit written permission.

Result: Commercial authorization NOT VERIFIED.

5. Independent Corroboration

AMFI source:
https://www.amfiindia.com/research-information/list-of-group-companies

AMFI provides company identity, ISIN and sector information for a limited group-company dataset.

Result: Partial corroboration only.

This dataset cannot establish complete NSE/BSE coverage.

6. Evidence Decision Matrix

Requirement| Status
Official NSE taxonomy| VERIFIED
Official methodology| VERIFIED
GFDL API field documentation| DOCUMENTED
Complete company coverage| NOT VERIFIED
Symbol + ISIN coverage| PARTIAL
Record-level provenance| NOT VERIFIED
Commercial authorization| NOT AUTHORIZED
Redistribution rights| NOT AUTHORIZED
Production API validation| NOT TESTED

7. Mandatory Production Controls

source_authenticity_status = "UNVERIFIED"
source_authenticity_verified = False
source_authorized_for_nse_mapping = False
commercial_use_authorized = False
redistribution_authorized = False
mapping_eligible = False
sector_mapping_activated = False

No inferred mapping from company names, tickers, index membership or third-party labels is permitted.

8. Required Next Actions

1. Obtain written GFDL source-provenance confirmation.
2. Obtain complete company-level Symbol and ISIN coverage details.
3. Obtain API documentation and sample production response.
4. Obtain commercial-use and redistribution permissions.
5. Validate records against official NSE identity and taxonomy evidence.
6. Run automated tests and GitHub Actions.
7. Keep Sector Mapping disabled until every approval condition passes.

9. Final Decision

HOLD — DO NOT ENABLE SECTOR MAPPING.

GFDL remains a candidate source, not an approved production source.

Public API documentation does not establish commercial licensing or official record-level provenance.

---

Project Checkpoint:
TLP-CP-2026-11-07-PHASE-04-CH25-STEP-21-SOURCE-AUTHENTICITY-REVIEW-COMPLETE-HOLD

Next: Complete source authorization and coverage verification before Step 22 approval.