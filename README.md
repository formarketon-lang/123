TradeLab Pro (TLP)

Indian Cash Market Analysis Platform

TradeLab Pro is a modular market-analysis platform focused on NSE and BSE cash equities. It is being developed with Python, Streamlit, and GitHub Actions, with an emphasis on verified market data, transparent calculations, and independently testable modules.

1. Project Scope

- Primary market: NSE Cash Equity
- Planned secondary market: BSE Cash Equity
- Application: Streamlit
- Language: Python
- Testing: pytest and GitHub Actions
- Deployment target: Streamlit Community Cloud

Futures and Options (F&O) Scanner is outside the current project scope.

2. Current Application Pages

The current application includes:

Relative Strength

- NSE equity universe-based stock selection
- Main benchmark comparison
- Multiple main benchmark selection
- Configurable return windows
- Market-cap filtering using AMFI classification
- Verified sector benchmark selection
- Stock and benchmark performance analysis

Stock Search

- Search NSE listed cash-equity securities
- Search by stock symbol or company name
- Display available security-master fields
- Refresh the NSE universe

Settings (Data)

- Active data-source configuration
- Exchange selection
- Historical date range
- Main benchmark selection
- Verified sector selection
- Market-cap selection

A global data-integrity alert area is also included in the application.

3. Market Data Policy

The active data-source configuration is:

NSE Primary → Yahoo Finance Secondary

Important rules:

- NSE is the primary source.
- Yahoo Finance is a secondary fallback.
- Data-source limitations must be visible.
- Unverified mappings must not be treated as approved.
- Missing data must not be replaced with fabricated values.
- Historical data must be validated before analysis.

CSV/Excel, broker APIs, and other providers must not be described as active scanner sources until their adapters are implemented and tested.

4. Exchange Support

NSE

NSE is the currently supported exchange for the active Relative Strength Scanner and Stock Search.

BSE

BSE is not yet enabled for scanner execution. Official security-universe validation and a validated BSE data pipeline are required before activation.

Both Exchanges

Combined NSE/BSE scanning remains disabled until both independent pipelines are verified.

5. Benchmark and Sector Mapping

Main benchmark mappings are maintained centrally in:

"data/benchmark_mapping.py"

Only configured benchmark mappings should be exposed to the application.

Sector comparison must use verified sector-index mappings and approved constituent membership evidence.

The currently configured sector mapping is limited. Sector Mapping Expansion must remain disabled until official classification and membership evidence passes validation.

6. Market Capitalization

The current market-cap classification uses AMFI's available half-yearly classification data.

- Large Cap
- Mid Cap
- Small Cap

Symbol and ISIN matching must be validated. This classification should not be represented as live daily market capitalization.

7. Project Architecture

The project follows a modular structure:

- "app.py" — Streamlit application entry point
- "ui/" — Application pages and presentation
- "core/" — Analysis and business logic
- "data/" — Data schema, adapters, mappings, and universe
- "tests/" — Automated tests
- "scripts/" — Audit and maintenance utilities
- ".github/workflows/" — Automated testing workflows
- ".streamlit/" — Streamlit configuration

Existing compatibility modules must be preserved until their dependencies and regression tests are verified.

8. Development and Testing

Install dependencies:

python -m pip install -r requirements.txt

Run the application:

streamlit run app.py

Run all tests:

python -m pytest -v

GitHub Actions runs automated tests on pushes and pull requests to the main branch.

9. Development Principles

1. No fake market data.
2. No unsupported stock or sector mappings.
3. Keep stock-versus-sector and stock-versus-main-index comparisons separate.
4. Preserve existing working functionality during upgrades.
5. Keep data adapters modular and replaceable.
6. Validate changes through automated tests.
7. Do not activate a new market-data provider without verification.
8. Maintain compatibility until dependent modules are migrated and tested.

10. Planned Development Roadmap

The broader roadmap includes:

- Existing TLP completion
- Market Intelligence
- Market Analysis Engine
- Technical Indicator Engine
- Support and Resistance Engine
- Market Breadth and Strength
- Market Indicators Center
- News and Events Engine
- Historical and Live Market Engine
- Integration, Testing and Deployment

These are planned modules, not claims that every module is currently implemented.

11. Project Status

TradeLab Pro is under active development.

Current priorities are data integrity, verified NSE security information, reliable Relative Strength calculations, maintainable architecture, and regression-safe expansion.

Project ID: TLP-MASTER-001
