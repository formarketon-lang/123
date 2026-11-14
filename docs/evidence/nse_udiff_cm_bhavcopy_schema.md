# NSE CM UDiFF Bhavcopy — Chapter 01 Evidence Record

Project: TLP-MIM-001  
Parent: TLP-MASTER-001  
Scope: NSE Cash Market, CM segment, STK instrument type, EQ series  
Status: PASS — official workbook field map and sample header verified; live membership identity/coverage remains REVIEW

## Official NSE references

1. NSE Forms & Formats — UDiFF standards, catalogue and CM Bhavcopy format/test-file links:  
   https://www.nseindia.com/static/resources/forms-formats-members

2. Current NSE UDiFF Trade and Bhavcopy file-format workbook linked from the official page (June 2026):  
   https://nsearchives.nseindia.com/web/mediaattachment/2026-06/UDiFF_trade_and_Bhavcopy_file_formats_20260630115803.xlsx

3. NSE UDiFF Bhavcopy sample archive linked from the official page:  
   https://nsearchives.nseindia.com/web/sites/default/files/inline-files/Bhavcopy.zip

4. NSE Circular NSE/MSD/62142, 22-May-2024 — UDiFF update. The circular records the revision of reserved tags to Rsvd1–Rsvd4 and removal of the trailing extra comma for the CM UDiFF Bhavcopy, effective 21-Jun-2024:  
   https://nsearchives.nseindia.com/web/sites/default/files/inline-files/MSD62142.zip

5. NSE Master Data Technical Specifications — Normal Market Eligibility and Security Status values:  
   https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_MasterData_Technical_Specifications.pdf

The official Forms & Formats page was observed to list the UDiFF catalogue through Version 4.0 and the CM Bhavcopy format/test files. The page shows an update date of 30-Jun-2026.

## Verified official schema evidence

GitHub Actions live evidence run:  
https://github.com/formarketon-lang/123/actions/runs/43550928359

Artifact: `tlp-ch01-nse-udiff-live-audit` (14-day retention)

- Official workbook SHA-256: `b9f2fa369af20381374cdb40c3ebc96c43029401e057225599cfe63b288ba3e8`
- Official sample ZIP SHA-256: `786a5ae1329f27a4f08af794737cb380e82de6a53db6751b518d2309512130fa`
- Workbook sheet verified: `Bhavcopy File Format`
- Official sample member verified: `Bhavcopy/BhavCopy_NSE_CM_0_0_0_20231207_F_0000.csv`
- Exact expected field-name to ISO-tag pairs: 14/14 matched.
- Official sample header: required CM UDiFF tags present.
- Production live header: required tags present; 34 columns parsed.

The mapping approval is pinned in `data/providers/nse_udiff_downloader.py` against these official source hashes. The live audit checks the raw production header again before the provenance audit can report schema PASS.

## Production ISO-tag mapping currently implemented

| Canonical field | UDiFF ISO tag | Use |
|---|---|---|
| Instrument ID | FinInstrmId | Exchange instrument identity |
| Observation Date | TradDt | Requested trade date |
| Segment | Sgmt | Must be CM |
| Source | Src | Must be NSE |
| Instrument Type | FinInstrmTp | Must be STK |
| ISIN | ISIN | Identity key |
| Symbol | TckrSymb | NSE trading symbol |
| Series | SctySrs | Must be EQ |
| Open | OpnPric | OHLC |
| High | HghPric | OHLC |
| Low | LwPric | OHLC |
| Close | ClsPric | Current close |
| Previous Close | PrvsClsgPric | Prior-session close |
| Volume | TtlTradgVol | Traded volume |

The production normalizer rejects missing required tags, wrong segment/source/instrument/series, mixed trade dates, invalid ISINs, duplicate EQ symbols, invalid/non-finite prices, and inconsistent current-session OHLC. Previous Close is intentionally excluded from current-session candle-range validation because a gap can place the prior close outside the current day's High/Low range.

## Implementation evidence

- Downloader: `data/providers/nse_udiff_downloader.py`
- Orchestration service: `services/market_intelligence/bhavcopy_service.py`
- Raw archive hash and provenance audit: `data/providers/nse_bhavcopy_provenance.py`
- Dated NSE MII identity reconciliation: `data/providers/nse_bhavcopy_mii_validation.py`
- Unit tests: `tests/test_nse_udiff_downloader.py`
- Service tests: `tests/test_market_intelligence_bhavcopy_service.py`
- Live verification workflow: `.github/workflows/ch01-udiff-live-check.yml`

## Outstanding evidence

The exact official Bhavcopy worksheet and official sample CSV header have now been downloaded and inspected in GitHub Actions. All 14 required field-name/ISO-tag pairs match the code map, and the official CM sample header contains the required tags. Schema mapping status is PASS. The official workbook and sample hashes are pinned in code and this evidence record.

A live 13-Nov-2026 UDiFF/MII comparison exposed two identity exceptions:

- `DCMFINSERV` is present in the raw same-date MII file as EQ, but its Normal Market Eligibility is `0` (not allowed in the Normal Market); its Auction Market Eligibility is `1`. The normalizer correctly excludes it from the verified normal-market universe. Its appearance in the UDiFF EQ file is retained as an explicit REVIEW exception and is not counted as a normal-market constituent.
- `BNAGROCHEM` appears in both sources, but the UDiFF row has Instrument ID `762608`, Series `EQ`, ISIN `INE00HZ01011`; the same-date MII EQ row has the same Instrument ID and Series but ISIN `INE00HZ01029`. The MII file also has the old ISIN `INE00HZ01011` under Series `IQ` and a different Instrument ID. Neither value is silently substituted. The observation is excluded from verified calculations and remains REVIEW pending authoritative identity resolution.

The reconciliation service now returns both exceptions, preserves the raw rows in the live evidence artifact, and excludes them from verified breadth inputs. The service also compares Instrument ID when available on both sides; it never treats a matching Symbol alone as sufficient identity evidence.

## Decision

- Official source reference: RECORDED
- Official endpoint transport: VERIFIED by HTTPS host allowlist
- Raw archive hash: RECORDED
- Live raw-field parsing: PASS — official NSE archive and required ISO tags verified in https://github.com/formarketon-lang/123/actions/runs/43550928359
- Symbol/ISIN reconciliation: REVIEW where unknown rows occur
- Official schema mapping approval: PASS
- Live MII identity/coverage: REVIEW
- Chapter 01 acceptance: ACCEPTED WITH REVIEW CONDITIONS

No sector mapping, BSE mapping, or F&O Scanner scope is authorized by this evidence record.
