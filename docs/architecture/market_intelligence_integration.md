# TradeLab Pro — Market Intelligence Integration Contract

Project ID: TLP-MASTER-001
Status: Architecture Approved for Implementation Planning
Scope: NSE/BSE Cash Equity
F&O Scanner: Excluded

## 1. Objective

Introduce Market Intelligence as a separate application module.

The new module must not break or replace:
- Relative Strength
- Stock Search
- Settings (Data)
- Global Data Integrity Monitor

## 2. Integration Principle

Market Intelligence must be modular and independently testable.

The application entry point (app.py) should only:
- Configure the Streamlit application
- Render global alerts
- Control navigation
- Route users to the selected page

Business logic must not be implemented inside app.py.

## 3. Planned Module Boundaries

### UI Layer
Planned file:
- ui/market_intelligence.py

Responsibilities:
- Render Market Intelligence page
- Display verified market information
- Collect user selections
- Present analysis results

UI must not independently fetch or calculate raw market data.

### Core Layer
Planned future modules:
- core/market_intelligence/
- Independent analysis and signal validation

Responsibilities:
- Market condition analysis
- Market breadth calculations
- Strength and weakness classification
- Signal validation
- Result generation

Core modules must not import Streamlit UI modules.

### Data Layer
Planned future modules:
- data/market_intelligence/
- Reusable data contracts and adapters

Responsibilities:
- Retrieve market data through approved adapters
- Validate source and timestamps
- Handle missing and incomplete observations
- Preserve data provenance

Data modules must not import UI or scripts.

## 4. Data Integrity Rules

1. NSE remains the primary source.
2. Yahoo Finance remains the secondary fallback.
3. Missing data must never be fabricated.
4. Every result must preserve its source information.
5. Unverified mappings must not be approved.
6. BSE remains disabled until its independent data pipeline is verified.
7. Sector Mapping Expansion remains OFF until official evidence is approved.

## 5. Application Navigation Contract

Existing pages:
- Relative Strength
- Stock Search
- Settings (Data)

Planned fourth page:
- Market Intelligence

The new page must be added without removing or renaming existing navigation entries.

Global Data Integrity Monitor must remain available across pages.

## 6. Testing Requirements

Before enabling the new page:

- Existing page smoke tests must pass.
- Market Intelligence must have independent UI tests.
- Core calculations must have independent unit tests.
- Data validation must have independent tests.
- Navigation integration must be tested.
- GitHub Actions must pass.

No existing tests may be deleted merely to make the new integration pass.

## 7. Future Extension Policy

The architecture should support adding:
- Market Regime Analysis
- Market Breadth
- Sector Strength
- Advance/Decline Analysis
- Index Participation
- Market Trend Classification
- News and Events Context

Each feature must have a defined data source, calculation method, validation rule and test coverage.

## 8. Activation Gate

Market Intelligence navigation must not be activated until:

- Its UI module exists.
- Its required core/data interfaces exist.
- Its page can render safely.
- Integration tests pass.
- Existing application regression tests pass.

## 9. Non-Negotiable Rules

- No fake market data.
- No unsupported market signals.
- No unverified sector mapping.
- No F&O Scanner.
- No unnecessary changes to working modules.
- Preserve backward compatibility until migration is verified.

End of Architecture Contract.
