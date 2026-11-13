
# TradeLab Pro — Market Intelligence Data Contract

Project ID: TLP-MIM-001
Parent Project: TLP-MASTER-001
Part: Market Intelligence
Chapter: 01
Step: 37
Status: REVIEW CANDIDATE — NOT APPROVED
Market Scope: NSE Cash Equity
F&O Scanner: Excluded

---

## 1. Purpose

This contract defines the data requirements, validation rules,
source provenance, service boundaries and activation restrictions
for Market Intelligence.

This document is a review candidate. It does not independently
approve production activation or authorize unsupported analysis.

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

Existing standardized fields include:

- Date
- Open
- High
- Low
- Close
- Volume
- Symbol
- Source
- Exchange
- Timeframe
- Fallback Reason

Market Intelligence index service additionally requires:

- Fetched At UTC
- Validation Status

The existing interfaces must be reviewed before adding
new adapters or duplicate data structures.

## 3. Source Priority

### 3.1 Primary Source

NSE official data sources, subject to validation.

### 3.2 Secondary Source

Yahoo Finance, only as a documented fallback.

### 3.3 Restricted Sources

- BSE remains disabled until independently verified.
- Unverified sector mappings must not be used.
- Vendor data requires source, license and reference approval.
- Demo or fabricated data must never enter production analysis.

Yahoo Finance must not silently replace failed NSE data.

Every fallback must preserve its actual source and reason.

## 4. Common Data Provenance Contract

Every future Market Intelligence result must preserve,
where applicable:

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

- Index Data Service validates Fetched At UTC.
- Breadth Service validates source, exchange, timeframe,
  fallback reason and observation date.
- Breadth Service does not currently require a Fetch Timestamp
  field in its stock observations.
- This is an outstanding contract implementation gap.
- Regime Service uses the validated Index Data Service.

Therefore, the common provenance contract is not yet
fully implemented across all services.

## 5. Analysis Data Requirements

### 5.1 Market Regime Analysis

Required:

- Verified index identifier
- Validated historical OHLCV observations
- Valid observation dates
- Source provenance
- Fetch timestamp in UTC
- Validation status

Current calculation method:

- Closing price
- Short moving average
- Long moving average
- Long moving average direction

No regime classification may be treated as approved
if its input data validation has failed.

### 5.2 Market Breadth

Required:

- Verified point-in-time stock universe
- Official NSE MII EQ identity evidence
- Valid stock observations for the selected date
- Advancing, declining and unchanged classification
- Valid denominator and coverage information
- Source and fallback provenance

Missing stocks must not be treated as unchanged.

A PASS requires complete verified membership coverage
and an aligned universe snapshot date.

### 5.3 Advance / Decline Analysis

Required:

- Valid stock universe for each observation date
- Previous and current valid closing prices
- Explicit treatment of missing observations
- Source and date provenance

Incomplete coverage must be disclosed.

### 5.4 Sector Strength

Required:

- Official sector membership evidence
- Verified sector benchmark mapping
- Valid stock and benchmark observations
- Membership audit status

Unverified membership must block sector-level conclusions.

Sector Mapping Expansion remains OFF.

### 5.5 Index Participation

Required:

- Verified index constituents
- Valid point-in-time membership
- Stock-level observations
- Index observation date
- Coverage statistics

Current membership must not be assumed to represent
historical membership.

### 5.6 Market Trend Classification

Required:

- Validated index or stock observations
- Documented calculation rules
- Explicit missing-data handling
- Independently tested classification logic

No unsupported trend label or signal may be displayed.

### 5.7 News and Events Context

Required:

- Identifiable source
- Article or event publication timestamp
- Retrieval timestamp
- Relevant instrument or index reference
- Source link and provenance

News context must remain separate from calculated
market indicators unless a future approved contract
defines their relationship.

## 6. Validation Rules

All analysis inputs must pass applicable checks:

1. Data must not be empty.
2. Dates must be valid.
3. Dates must be ordered.
4. Duplicate observations must be detected.
5. Required numeric fields must be valid.
6. Prices must be positive and finite.
7. OHLC relationships must be consistent.
8. Volume must not be negative or malformed.
9. Exchange and symbol identity must be verified.
10. Source provenance must be preserved.
11. Fetch timestamps must be valid and timezone-aware.
12. Missing observations must not be fabricated.
13. Unverified mappings must be rejected.
14. Fallback reasons must be preserved when applicable.

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

A failed or unavailable source must not produce
a successful analysis result.

A REVIEW result must not be represented as a verified PASS.

## 8. Failure and Fallback Policy

If NSE Primary fails:

1. Record the primary failure.
2. Use Yahoo only where the existing adapter permits it.
3. Preserve the fallback reason.
4. Validate the returned data independently.
5. Mark the result with its actual source.
6. Block analysis if required validation fails.

No automatic substitution of missing values is allowed.

A Yahoo result must never be labelled as NSE data.

## 9. Service Boundaries

### Data Layer

Responsibilities:

- Retrieval through approved adapters
- Normalization
- Provenance preservation
- Source validation
- Timestamp validation
- Missing and incomplete observation handling

Data must not depend on Core, UI or Scripts.

### Core Layer

Responsibilities:

- Market calculations
- Classification logic
- Coverage evaluation
- Result generation

Core must not import Streamlit UI modules.

### Service Layer

Responsibilities:

- Coordinate Data and Core
- Enforce service-level input requirements
- Preserve provenance in returned results
- Propagate validation failures
- Prevent REVIEW or BLOCKED data from being represented as PASS

### UI Layer

Responsibilities:

- User selections
- Safe result presentation
- Clear status display
- Validation and coverage warnings

UI must not fetch raw market data or implement
business calculations.

## 10. Testing Requirements

Before activation, tests must cover:

- Valid and invalid source metadata
- Missing and duplicate observations
- Invalid OHLC values
- Non-finite prices
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

A passing test suite does not independently prove
that every contract requirement is implemented.

## 11. Current Review Findings

The following findings are recorded from repository review.

### 11.1 Index Data Service

- Requires standardized OHLCV and provenance metadata.
- Validates symbol and NSE exchange identity.
- Validates source and daily timeframe.
- Validates Yahoo fallback reason.
- Validates timezone-aware Fetched At UTC.
- Rejects duplicate and unordered dates.
- Rejects invalid or non-finite OHLC values.
- Allows null index volume but rejects malformed,
  non-finite or negative non-null volume.

Review status: IMPLEMENTATION REVIEWED.

### 11.2 Breadth Core

- Validates official NSE MII identity fields.
- Requires EQ series and NSE exchange.
- Validates ISIN format and uniqueness.
- Rejects duplicate symbols.
- Checks universe snapshot date against observation date.
- Requires exact membership coverage for PASS.

Review status: IMPLEMENTATION REVIEWED.

### 11.3 Breadth Service

- Requires NSE observations.
- Requires daily timeframe.
- Requires Validation Status PASS.
- Requires Yahoo fallback reason.
- Requires MII_DATED universe verification.
- Checks observation date consistency.

Outstanding gap:

- Fetch Timestamp in UTC is not currently a required
  stock observation field in REQUIRED_STOCK_FIELDS.

Review status: REVIEW — PROVENANCE GAP OPEN.

### 11.4 Regime Core and Service

- Regime Service uses the validated index data service.
- Core checks moving-average windows and minimum observations.
- Result preserves source and validation status.
- Invalid or unverified source status cannot receive analysis PASS.

Review status: IMPLEMENTATION REVIEWED.

## 12. Contract Approval Gates

The contract may be approved only after:

1. All mandatory provenance requirements are implemented.
2. Breadth Service timestamp gap is resolved or formally
   excluded through an explicitly approved contract decision.
3. Core and Data service boundaries are verified.
4. Existing tests and required new tests pass.
5. Navigation integration tests pass.
6. Existing application regression tests pass.
7. GitHub Actions results are verified.
8. Final review evidence is recorded.

Until these gates are satisfied, contract status remains
REVIEW CANDIDATE — NOT APPROVED.

## 13. Activation Gate

Market Intelligence remains inactive until:

- Data interfaces are implemented and verified.
- Core calculations are implemented and tested.
- Provenance and validation tests pass.
- Navigation integration tests pass.
- Existing application regression tests pass.
- GitHub Actions are successful.
- Contract approval is recorded.

A UI shell alone does not authorize activation.

## 14. Non-Negotiable Rules

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

Current decision: REVIEW — NOT APPROVED.

Open item:
Breadth Service fetch timestamp provenance requirement.

Next action:
Resolve the open provenance gap, run targeted tests,
and submit the contract for final approval.

CH01 STATUS: NOT ACCEPTED
CH02 STATUS: NOT STARTED

End of Market Intelligence Data Contract.
