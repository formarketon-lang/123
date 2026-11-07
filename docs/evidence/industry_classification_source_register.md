TradeLab Pro — Industry Classification Source Evidence Register

Project ID: TLP-MASTER-001
Part: 04
Chapter: 25
Step: 20 — Independent Source Evidence & Verification Design
Status: DOCUMENTATION PREPARED — AWAITING GITHUB COMMIT
Last Updated: 2026-11-07

---

1. Purpose

This document records the independent evidence status of the company-level industry classification source required by TradeLab Pro.

The objective is to establish a verifiable, authorized and commercially permissible source for NSE company-level classification before enabling sector mapping.

TradeLab Pro supports NSE and BSE cash equities only. It does not include an F&O scanner.

2. Official NSE Classification Sources

Source A — NSE Indices Industry Classification

URL: https://www.niftyindices.com/resources/industry-classification

Verified information:

- NSE Indices publishes a four-tier industry classification framework.
- Macro Economic Sectors: 12
- Sectors: 22
- Industries: 59
- Basic Industries: 197

Verification result: OFFICIAL TAXONOMY FRAMEWORK VERIFIED

Limitation: This framework does not itself establish a complete downloadable company-level Symbol and ISIN mapping.

Source B — NSE Indices Industry Classification Guideline, July 2023

URL: https://www.niftyindices.com/docs/default-source/default-document-library/industry-classification/nse-indices_industry-classification-guideline-2023-07.pdf?sfvrsn=d89dd39_1

Verified information:

- Classification methodology is based on company business activities and revenue.
- Audited consolidated annual financial statements are a primary information source.
- Classification may be reviewed periodically or following relevant corporate events.
- The document includes restrictions concerning commercial use and unauthorized dissemination.

Verification result: METHODOLOGY DOCUMENT VERIFIED

Commercial use and licensing: NOT AUTHORIZED / NOT VERIFIED

Official contact: indices@nse.co.in

Source C — NSE Indices Industry Classification Structure, July 2023

URL: https://www.niftyindices.com/docs/default-source/default-document-library/industry-classification/nse-indices_industry-classification-structure-2023-07.pdf?sfvrsn=c89dd39_1

Verified information:

- Provides classification hierarchy, codes and definitions.
- Supports exact taxonomy-path validation.

Limitation: Does not establish complete company-level Symbol and ISIN assignments.

Verification result: TAXONOMY STRUCTURE VERIFIED — COMPANY MAPPING NOT VERIFIED

Source D — NSE Securities Available for Trading

URL: https://www.nseindia.com/static/market-data/securities-available-for-trading

Purpose:

- Security identity and trading-availability evidence.
- Can support NSE security master verification.

Limitation: Security identity data is not company-level industry classification.

Verification result: IDENTITY SOURCE ONLY

3. External Provider Evidence — Global Datafeeds

Provider: Global Datafeeds

API information requested: "GetSectoralClassification"

Support ticket: 39451

Acknowledgement received: 2026-11-07

Email subject: TradeLab Pro – Enquiry for NSE/BSE Official Company-Level Sectoral Classification API and Commercial Licensing

Current status:

- Support request acknowledged.
- Substantive technical response pending.
- Official source provenance not independently verified.
- Company-level Symbol and ISIN coverage not verified.
- Commercial licensing not verified.
- Redistribution and display rights not verified.

Decision: DO NOT APPROVE AS NSE OFFICIAL SOURCE YET

4. NSE Communication Status

Recipient: indices@nse.co.in

Subject: Request for Official Company-Level NSE Industry Classification Dataset / API

Status as of 2026-11-07:

- Request sent.
- No incoming response verified yet.
- Official company-level dataset/API availability remains unconfirmed.
- Commercial permission remains unconfirmed.

5. Independent Evidence Decision Matrix

Requirement| Current Status
Official NSE taxonomy framework| VERIFIED
Official classification methodology| VERIFIED
Complete company-level classification dataset| NOT VERIFIED
Symbol + ISIN coverage| NOT VERIFIED
Independent source authenticity| NOT VERIFIED
API access and documentation| NOT VERIFIED
Commercial usage authorization| NOT VERIFIED
Redistribution/display rights| NOT VERIFIED
Independent authenticity verifier| NOT IMPLEMENTED

6. Production Safety Controls

The following controls must remain enforced until independent evidence is available:

source_authenticity_status = "UNVERIFIED"
source_authenticity_verified = False
source_authorized_for_nse_mapping = False
mapping_eligible = False
sector_mapping_activated = False

No source may be approved solely because an operator declares it to be official.

A filename, URL, source label, API response, or SHA-256 hash alone does not establish official authenticity or commercial authorization.

No inferred mapping from company names, tickers, third-party sector labels or index membership is permitted.

7. Step 20 Completion Conditions

Step 20 can be closed only after:

1. Independent evidence of the source owner and authenticity is obtained.
2. Written confirmation of company-level Symbol and ISIN coverage is obtained.
3. Technical API or dataset documentation is obtained and reviewed.
4. Commercial usage, storage, display and redistribution rights are confirmed in writing.
5. The source is independently validated against NSE identity and official taxonomy evidence.
6. Required audit tests and GitHub Actions pass.

8. Final Decision

Current decision: HOLD — DO NOT ENABLE SECTOR MAPPING.

Official NSE taxonomy and methodology are verified, but a complete authorized company-level classification source has not yet been established.

TradeLab Pro must continue operating with sector mapping disabled until all required evidence and authorization conditions are satisfied.

---

Project Checkpoint: "TLP-CP-2026-11-07-PHASE-04-CH25-STEP-20-EVIDENCE-REGISTER-PREPARED"

Next Action: Commit this evidence register to the main repository and verify GitHub Actions.
