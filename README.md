# TradeLab Pro — Phase 1 Foundation

This is the modular project foundation for the agreed Settings (Data) and Relative Strength scope.

## Included in Phase 1
- Streamlit app entry point and navigation
- Settings form scaffold with the agreed 16 data-source names, NSE/BSE/Both, date range and 14 benchmarks
- Relative Strength form scaffold with sector, optional stock search, Market Cap toggle, Date-Based RS toggle, Average RS toggle and timeframe selection
- Initial RS calculation functions with unit tests
- Dark theme and Git ignore rules

## Important
Phase 1 is a UI and architecture scaffold. The forms do not yet connect to live APIs, fetch historical data, highlight official exchange holidays, calculate the complete RS result tables, or render the final candlestick/volume chart. Those will be implemented and tested in later phases.

## Run locally
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Run tests
```bash
python -m pytest -q
```

## Secrets
Do not commit API keys or broker credentials. Use Streamlit secrets or environment variables in later phases.
