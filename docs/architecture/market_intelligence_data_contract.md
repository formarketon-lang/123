# TradeLab Pro — Market Intelligence Data Contract

Project ID: TLP-MIM-001  
Parent Project: TLP-MASTER-001  
Part: Market Intelligence  
Chapter: 01  
Step: 37  
Status: APPROVED — REVIEW-AWARE NSE CASH-MARKET FOUNDATION  
Market Scope: NSE Cash Equity  
F&O Scanner: Excluded

---

## 1. Purpose

This contract defines the data requirements, validation rules,
source provenance, service boundaries and activation restrictions
for Market Intelligence.

This contract is approved for the review-aware NSE cash-market
foundation under the conditions recorded in the Review Decision.
It does not approve incomplete live datasets as PASS, authorize
unsupported analysis, or enable BSE / sector expansion.

Existing Data Layer interfaces must be reused where suitable.
No duplicate market-data adapter may be introduced.

## 2. Existing Data Layer

The following existing modules are the starting point:

- `data/schema.py`
- `data/market_data_adapter.py`
- `data/benchmark_mapping.py`
- `data/universe.py`
- `data/constituent_audit.py`
- `data/market_intelligence/index_service.py`

Existing standardized fields include Date, Open, High, Low,
Close, Volume, Symbol, Source, Exchange, Timeframe and
Fallback Reason.

Market Intelligence index and breadth services additionally
validate Fetched At UTC and Validation Status.

Existing interfaces must be reviewed before adding new adapters
or duplicate data structures.

## 3. Source Priority

### Primary source

NSE official data sources, subject to validation.

### Secondary source

Yahoo Finance, only as a documented fallback.

### Restricted sources

- BSE remains disabled until independently verified.
- Unverified sector mappings must not be used.
- Vendor data requires source, license and reference approval.
- Demo or fabricated data must never enter production analysis.

Yahoo Finance must not silently replace failed NSE data.
Every fallback must preserve its actual source and reason.

## 4. Common Data Provenance Contract

Every Market Intelligence observation must preserve, where
applicable:

- Symbol or index identifier
- Exchange
- Observation date
- Data source
- Fetch timestamp in UTC
- Validation status
- Fallback reason, when applicable
- Relevant benchmark or universe reference

A missing provenance field must never be silently invented.
A service may return PASS only when all provenance fields
required for that service have been validated.

Current implementation review:

- Index Data Service validates timezone-aware Fetched At UTC.
- Breadth Service requires and validates Fetched At UTC.
- Breadth Service validates source, exchange, timeframe,
  fallback reason, observation date and universe evidence.
- Regime Service uses the validated Index Data Service.
- NSE Equity and Index downloaders capture a timezone-aware UTC
  retrieval timestamp from the completed HTTP response.
- Market Data Adapter preserves the downloader timestamp in
  the common provenance fields.
- Live NSE verification confirmed actual NSE source provenance,
  timestamp propagation and continuous daily coverage for MARICO
  and all six configured NSE index/sector benchmarks.
- NSE UDiFF normalizer requires an explicit timezone-aware
  fetched_at_utc argument and emits Fetched At UTC.
- A production NSE CM UDiFF downloader now retrieves the official
  final archive over HTTPS, records the actual response retrieval
  timestamp and SHA-256, validates the raw ISO tags, final session
  identifier and numeric Instrument ID, and normalizes only
  NSE / CM / STK / EQ rows.
- The official NSE UDiFF workbook's `Bhavcopy File Format` sheet
  and official CM sample CSV header were downloaded and inspected.
  All 14 required field-name / ISO-tag pairs matched. Workbook and
  sample SHA-256 values are pinned in the UDiFF downloader and
  recorded in the NSE UDiFF evidence register.
- A production Bhavcopy service requires an exact-date MII_DATED
  universe, reconciles Symbol + ISIN, excludes unverified rows from
  breadth calculations, and preserves identity exceptions.
- Live 13-Nov-2026 UDiFF data parsed successfully. The live identity
  audit exposed DCMFINSERV as not eligible for Normal Market and a
  BNAGROCHEM Symbol/ISIN mismatch. Both are excluded from verified
  breadth observations and remain REVIEW. The same-date MII universe
  has 2,762 eligible rows; 2,742 observations reconcile exactly,
  producing 99.2759% coverage and a REVIEW result. Missing rows are
  not treated as unchanged.

The standard NSE Equity/Index timestamp handoff is verified.
The production UDiFF downloader, official schema mapping and
production service are implemented and verified. Live identity
exceptions and incomplete daily membership coverage are correctly
returned as REVIEW; unverified rows are excluded and missing
members are not counted as unchanged. This is an approved,
review-aware NSE cash-market contract, not a claim that every
daily live dataset is PASS. Test-only timestamps are fixtures
and must never be used as production data.

## 5. Analysis Data Requirements

### Market Regime Analysis

Required: verified index identifier, validated historical OHLCV,
valid observation dates, source provenance, fetch timestamp in UTC
and validation status.

Current calculation inputs include closing price, short moving
average, long moving average and long moving average direction.
Invalid input data must block approved regime classification.

### Market Breadth

Required: verified point-in-time stock universe, official NSE MII
EQ identity evidence, valid stock observations, advancing/declining/
unchanged classification, denominator and coverage, and source
and fallback provenance.

Missing stocks must not be treated as unchanged. PASS requires
complete verified membership coverage and an aligned snapshot date.

### Advance / Decline Analysis

Required: valid stock universe for each observation date,
previous and current valid closing prices, explicit treatment
of missing observations, and source/date provenance.

Incomplete coverage must be disclosed.

### Sector Strength

Required: official sector membership evidence, verified sector
benchmark mapping, valid stock and benchmark observations, and
membership audit status.

Unverified membership must block sector-level conclusions.
Sector Mapping Expansion remains OFF.

### Index Participation

Required: verified index constituents, point-in-time membership,
stock-level observations, index observation date and coverage.
Current membership must not be assumed to represent historical
membership.

### Market Trend Classification

Required: validated index or stock observations, documented
calculation rules, explicit missing-data handling and independently
tested classification logic. No unsupported trend label or signal
may be displayed.

### News and Events Context

Required: identifiable source, publication timestamp, retrieval
timestamp, relevant instrument/index reference, source link and
provenance.

News context remains separate from calculated market indicators
unless an approved contract defines their relationship.

## 6. Validation Rules

All analysis inputs must pass applicable checks:

1. Data must not be empty.
2. Dates must be valid and ordered.
3. Duplicate observations must be detected.
4. Required numeric fields must be valid.
5. Prices must be positive and finite.
6. OHLC relationships must be consistent.
7. Volume must not be negative or malformed.
8. Exchange and symbol identity must be verified.
9. Source provenance must be preserved.
10. Fetch timestamps must be valid and timezone-aware.
11. Missing observations must not be fabricated.
12. Unverified mappings must be rejected.
13. Fallback reasons must be preserved when applicable.

Existing validation functions should be reused where suitable.
No silent sorting, filling, substitution or repair is allowed
unless a separately documented and tested policy authorizes it.

## 7. Data Status Contract

Services may expose these explicit states:

- `PASS` — required validation completed.
- `REVIEW` — evidence or coverage needs review.
- `BLOCKED` — required validation failed.
- `UNAVAILABLE` — required source data could not be obtained.
- `PENDING` — implementation or verification is incomplete.

A failed or unavailable source must not produce a successful
analysis result. REVIEW must never be represented as verified PASS.

## 8. Failure and Fallback Policy

If NSE Primary fails:

1. Record the primary failure.
2. Use Yahoo only where the existing adapter permits it.
3. Preserve the fallback reason.
4. Validate returned data independently.
5. Mark the result with its actual source.
6. Block analysis if required validation fails.

No automatic substitution of missing values is allowed.
A Yahoo result must never be labelled as NSE data.

## 9. Proposed Service Boundaries

### Data Layer

Responsibilities: retrieval through approved adapters,
normalization, provenance preservation, source and timestamp
validation, and missing/incomplete observation handling.

Data must not depend on Core, UI or Scripts.

### Core Layer

Responsibilities: market calculations, classification logic,
coverage evaluation and result generation.

Core must not import Streamlit UI modules.

### Service Layer

Responsibilities: coordinate Data and Core, enforce service-level
input requirements, preserve provenance, propagate validation
failures, and prevent REVIEW/BLOCKED data from being represented
as PASS.

### UI Layer

Responsibilities: user selections, safe result presentation,
clear status display, and validation/coverage warnings.

UI must not fetch raw market data or implement business
calculations.

## 10. Testing Requirements

Before activation, tests must cover:

- Valid and invalid source metadata
- Missing and duplicate observations
- Invalid OHLC values and non-finite prices
- Invalid volume
- Invalid or timezone-naive fetch timestamps
- Unordered dates
- NSE failure and Yahoo fallback provenance
- Missing fallback reason
- Incomplete stock-universe coverage
- Historical constituent membership
- Unverified sector mapping rejection
- Data freshness and timestamp handling
- Core calculation correctness
- UI integration and existing-page regression

Existing tests must not be deleted to make new tests pass.
A passing test suite does not independently prove that every
contract requirement is implemented.

## 11. Activation Gate

Market Intelligence remains inactive until all of the following
are verified:

- Data interfaces are implemented and verified.
- Core calculations are implemented and tested.
- Provenance and validation tests pass.
- Navigation integration tests pass.
- Existing application regression tests pass.
- GitHub Actions are successful.
- Contract approval and final review evidence are recorded.

A UI shell alone does not authorize activation.

## 12. Non-Negotiable Rules

- No fake market data.
- No fabricated market signals.
- No unsupported sector mappings.
- No silent source substitution.
- No automatic deletion of existing files or tests.
- No F&O Scanner.
- BSE remains disabled until independently verified.
- Sector Mapping Expansion remains OFF.

---

## Review Decision

Current decision: APPROVED — REVIEW-AWARE NSE CASH-MARKET FOUNDATION.

Approval conditions:
1. DCMFINSERV is formally classified as outside the Normal Market
   because its same-date MII row has Normal Market Eligibility 0
   and Auction Market Eligibility 1. It remains excluded from
   Normal-Market breadth.
2. BNAGROCHEM's Symbol/ISIN mismatch remains an explicit identity
   exception. No identifier substitution is permitted; the row
   remains excluded until authoritative NSE evidence resolves it.
3. The 20 MII members without a matching daily Bhavcopy observation
   remain missing, not unchanged. The live breadth result stays
   REVIEW at 99.2759% coverage until coverage is complete.
4. The UI must continue to show REVIEW and exclude unverified rows.
   BSE remains disabled and Sector Mapping Expansion remains OFF.

Verified activation gates:
- Data interfaces are implemented and verified.
- Core calculations are implemented and tested.
- Provenance and validation tests pass.
- Navigation integration tests pass.
- Existing application regression tests pass.
- GitHub Actions are successful.

This approval does not mark the 13-Nov-2026 live breadth data as
PASS. It approves the data contract and the safe REVIEW-aware
NSE implementation. Test-only timestamps are fixtures and must
never be used as production data.

CH01 STATUS: ACCEPTED WITH REVIEW CONDITIONS  
CH02 STATUS: NOT STARTED

End of Market Intelligence Data Contract.
