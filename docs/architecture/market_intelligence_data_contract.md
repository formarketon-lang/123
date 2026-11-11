
# TradeLab Pro — Market Intelligence Data Contract

Project ID: TLP-MASTER-001  
Part: Market Intelligence  
Chapter: 1  
Step: 24  
Status: Contract Draft — Pending Commit and Review  
Market Scope: NSE Cash Equity  
F&O Scanner: Excluded

---

## 1. Purpose

Define the data requirements and validation boundaries for
Market Intelligence before implementing its analysis engine.

This contract does not activate Market Intelligence,
generate market signals, or introduce new data providers.

Existing Data Layer interfaces must be reused where suitable.

## 2. Existing Data Layer

The following existing modules are the starting point:

- `data/schema.py`
- `data/market_data_adapter.py`
- `data/benchmark_mapping.py`
- `data/universe.py`
- `data/constituent_audit.py`

Existing standardized OHLCV fields include:

- Date
- Open
- High
- Low
- Close
- Volume
- Symbol
- Source

The market-data adapter also provides Exchange,
Timeframe and Fallback Reason metadata.

These existing interfaces must be reviewed before any
new implementation is introduced.

No duplicate market-data adapter should be created.

## 3. Source Priority

### Primary

NSE official data sources, subject to validation.

### Secondary

Yahoo Finance, only as a documented fallback.

### Restricted

- BSE remains disabled until independently verified.
- Unverified sector mappings must not be used.
- Vendor data requires source, license and reference approval.
- Demo or fabricated data must never enter production analysis.

Yahoo data must not silently replace failed NSE data.
Fallback use must remain identifiable.

## 4. Common Data Provenance Contract

Every future Market Intelligence result must preserve:

- Symbol or index identifier
- Exchange
- Observation date
- Data source
- Fetch timestamp in UTC
- Validation status
- Fallback reason, when applicable
- Relevant benchmark or universe reference

The fetch timestamp and validation envelope are proposed
contract requirements. They are not claims that the current
OHLCV DataFrame already provides all these fields.

Missing provenance must not be silently invented.

## 5. Analysis Data Requirements

### 5.1 Market Regime Analysis

Required:
- Verified index identifier
- Validated historical OHLCV observations
- Observation dates
- Source provenance

No regime classification until the required data and
calculation rules are independently tested.

### 5.2 Market Breadth

Required:
- Verified point-in-time stock universe
- Valid stock observations for the selected date
- Advancing, declining and unchanged classification
- Valid denominator and coverage information

Missing stocks must not be treated as unchanged.

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

All future analysis inputs must pass applicable checks:

1. Data must not be empty.
2. Dates must be valid and ordered.
3. Duplicate observations must be detected.
4. Required numeric fields must be valid.
5. Prices must be positive.
6. OHLC relationships must be consistent.
7. Exchange and symbol identity must be verified.
8. Source provenance must be preserved.
9. Missing observations must not be fabricated.
10. Unverified mappings must be rejected.

Existing validation functions should be reused where suitable.

## 7. Data Status Contract

Future services may expose these explicit states:

- `PASS` — required validation completed.
- `REVIEW` — evidence or coverage needs review.
- `BLOCKED` — required validation failed.
- `UNAVAILABLE` — required source data could not be obtained.
- `PENDING` — implementation or verification is incomplete.

A failed or unavailable source must not produce a
successful analysis result.

## 8. Failure and Fallback Policy

If NSE Primary fails:

1. Record the primary failure.
2. Use Yahoo only where the existing adapter permits it.
3. Preserve the fallback reason.
4. Validate the returned data independently.
5. Mark the result with its actual source.
6. Block analysis if required validation fails.

No automatic substitution of missing values is allowed.

## 9. Proposed Service Boundaries

Future implementation should keep responsibilities separate:

- Data Layer: retrieval, normalization, provenance and validation.
- Core Layer: calculations and classification.
- UI Layer: user selections and result presentation.

The UI must not fetch raw market data or implement
business calculations.

Core must not import Streamlit UI modules.

Data must not depend on Core, UI or Scripts.

## 10. Testing Requirements

Before activation, tests must cover:

- Valid and invalid source metadata
- Missing and duplicate observations
- Invalid OHLC values
- NSE failure and Yahoo fallback provenance
- Incomplete stock-universe coverage
- Historical constituent membership
- Unverified sector mapping rejection
- Data freshness and timestamp handling
- Core calculation correctness
- UI integration and existing-page regression

Existing tests must not be deleted to make new tests pass.

## 11. Activation Gate

Market Intelligence remains inactive until:

- Data interfaces are implemented and verified.
- Core calculations are implemented and tested.
- Provenance and validation tests pass.
- Navigation integration tests pass.
- Existing application regression tests pass.
- GitHub Actions are successful.

## 12. Non-Negotiable Rules

- No fake market data.
- No fabricated market signals.
- No unsupported sector mappings.
- No silent source substitution.
- No automatic deletion of existing files or tests.
- No F&O Scanner.
- BSE remains disabled pending verification.
- Sector Mapping Expansion remains OFF.

---

End of Market Intelligence Data Contract.
