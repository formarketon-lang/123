TradeLab Pro — Chapter 25, Step 04

Official Evidence and Provider Authorization Reconciliation

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 04
Review date: 2026-11-07
Decision: HOLD — DO NOT ENABLE SECTOR MAPPING

1. Objective

Reconcile official classification evidence, company-level coverage, provider documentation, source provenance and commercial authorization before approving any production sector mapping.

2. NSE Official Classification

Official source:
https://www.nseindia.com/static/products-services/industry-classification

Verified:

- NSE Indices publishes a four-level industry classification framework.
- The hierarchy is Macro Economic Sector, Sector, Industry and Basic Industry.
- Classification is based on company business activity and revenue.
- Audited consolidated annual financials are the primary source.
- Classification is reviewed annually.

Not verified:

- Complete downloadable NSE EQ company-level Symbol + ISIN mapping.
- Current complete company-level classification coverage.
- A production-ready official dataset with independently verified record-level provenance.

Decision: OFFICIAL TAXONOMY VERIFIED; COMPLETE COMPANY MAPPING NOT VERIFIED.

3. GFDL API Documentation

Documentation:
https://docs.globaldatafeeds.in/getsectoralclassification-15575605e0

Documented fields include:

- Symbol
- ScripCode
- CompanyName
- ISIN
- MacroEconomicIndicator
- Sector
- Industry
- BasicIndustry
- Classification codes and timestamps

The documentation displays an example response and states that actual data is returned as of 27 February 2025.

Not verified:

- Complete NSE EQ coverage.
- Complete BSE coverage.
- Current production response.
- Independent record-level provenance against NSE Indices.
- Commercial and redistribution authorization for TradeLab Pro.

Decision: API FIELD STRUCTURE DOCUMENTED; PRODUCTION SOURCE NOT APPROVED.

4. GFDL Licensing Review

Purchase conditions:
https://globaldatafeeds.in/global-datafeeds-apis/global-datafeeds-apis/pricing-sales/who-can-purchase/

Terms:
https://globaldatafeeds.in/terms-and-conditions/

Public purchase conditions state that the APIs are available for individual personal use. Commercial use requires applicable exchange agreements and fees.

Published terms state that data may not be redistributed without explicit written permission.

Decision:

- Personal-use conditions: DOCUMENTED.
- Commercial use authorization for TLP: NOT VERIFIED.
- Redistribution authorization for TLP: NOT VERIFIED.
- Exchange agreement: NOT PROVIDED.
- Written permission: NOT PROVIDED.

No production use or redistribution is authorized by this review.

5. Gmail Support Ticket 39451

Provider: Global Financial Datafeeds LLP Support
Ticket: 39451
Subject: TradeLab Pro – Enquiry for NSE/BSE Official Company-Level Sectoral Classification API and Commercial Licensing
Acknowledgement date: 2026-11-07

The received email confirms that the request was received and that the support team will review it and respond.

It does not confirm:

- Source provenance.
- Complete NSE/BSE coverage.
- Commercial use permission.
- Redistribution permission.
- Production API access or validation.

Decision: ACKNOWLEDGEMENT RECEIVED; SUBSTANTIVE RESPONSE PENDING.

6. Evidence Decision Matrix

Requirement| Status
Official NSE taxonomy| VERIFIED
Official NSE methodology| VERIFIED
GFDL API field documentation| DOCUMENTED
Complete NSE EQ company coverage| NOT VERIFIED
Complete BSE company coverage| NOT VERIFIED
Record-level official provenance| NOT VERIFIED
Current production API validation| NOT TESTED
Commercial authorization| NOT AUTHORIZED
Redistribution permission| NOT AUTHORIZED
GFDL substantive support response| PENDING

7. Mandatory Production Controls

source_authenticity_status = "UNVERIFIED"
source_authenticity_verified = False
source_authorized_for_nse_mapping = False
commercial_use_authorized = False
redistribution_authorized = False
mapping_eligible = False
sector_mapping_activated = False

No inferred classification from company names, tickers, index membership or third-party labels is permitted.

8. Required Next Actions

1. Obtain written GFDL source-provenance confirmation.
2. Obtain complete NSE and BSE company-level coverage details.
3. Obtain a current sample production API response.
4. Obtain written commercial-use authorization.
5. Obtain explicit redistribution permission, if required by the intended TLP distribution model.
6. Verify classification records against official NSE identity and taxonomy evidence.
7. Run automated tests and GitHub Actions after evidence integration.

9. Final Decision

HOLD — DO NOT ENABLE SECTOR MAPPING.

NSE taxonomy is verified, but complete company-level mapping is not established. GFDL documentation describes the API structure, but its source provenance, complete coverage and TLP commercial permissions remain unverified.

GFDL remains a candidate source, not an approved production source.

---

Project Checkpoint:
"TLP-CP-2026-11-07-CH25-STEP-04-EVIDENCE-RECONCILIATION-HOLD"

Next: Obtain substantive provider response and complete company-level coverage evidence before Step 05 approval.
