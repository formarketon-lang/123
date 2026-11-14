# TLP-MIM-001 — Chapter 01 Final Acceptance Register

Project ID: TLP-MIM-001  
Repository: formarketon-lang/123  
Branch: main  
Chapter: 01  
Status: ACCEPTED WITH REVIEW CONDITIONS  
Checkpoint: TLP-CP-2026-11-14-TLP-MIM-001-CH01-ACCEPTED-REVIEW-AWARE  
Scope: NSE Cash Market Intelligence  
F&O Scanner: Excluded

## 1. Purpose

This register records the implementation, test, integration,
and evidence gates for formal Chapter 01 acceptance.

Acceptance means the NSE Market Intelligence foundation,
review-aware services, official schema mapping, UI integration
and regression gates are verified. It does not mean every daily
live market dataset must return PASS.

## 2. Verified Implementation Baseline

Latest verified main commit:
`f5d77d0994fcc077a13009ac53ed5195e4f95c46`

TradeLab Pro Tests:
https://github.com/formarketon-lang/123/actions/runs/43551356536

Verified result: **614/614 tests passed**.

Yahoo Adapter Unit Tests:
https://github.com/formarketon-lang/123/actions/runs/43550928337

Verified result: **56/56 tests passed**.

Live NSE UDiFF verification:
https://github.com/formarketon-lang/123/actions/runs/43550928359

Verified workflow result: SUCCESS. The live data audit itself
correctly returns REVIEW for incomplete membership coverage
and the identified identity exceptions.

## 3. Verified Implementation

### Data and production services

- `data/providers/nse_udiff_downloader.py`
- `data/providers/nse_bhavcopy_mii_validation.py`
- `data/providers/nse_bhavcopy_provenance.py`
- `services/market_intelligence/bhavcopy_service.py`
- `data/market_intelligence/index_service.py`
- `services/market_intelligence/breadth_service.py`
- `services/market_intelligence/regime_service.py`

### Core

- `core/market_intelligence/breadth.py`
- `core/market_intelligence/regime.py`

### UI and navigation

- `ui/market_intelligence.py`
- `app.py`
- `tests/test_market_intelligence_navigation.py`

Market Intelligence is available in app navigation. The UI uses
the service layer, displays source/provenance and REVIEW states,
and does not import Core or Data directly.

Market Regime and Market Breadth are integrated. Advance /
Decline, Sector Strength, Index Participation, Market Trend
Classification and News and Events Context remain roadmap items.

## 4. Acceptance Gate Register

| Gate | Final Status | Evidence |
|---|---|---|
| Core implementation | PASS | Breadth and regime modules; core tests |
| Data service | PASS | NSE UDiFF downloader, MII reconciliation, provenance and service tests |
| Official UDiFF schema mapping | PASS | Official workbook and sample ZIP; 14/14 field/tag pairs |
| Breadth and regime tests | PASS | Core and service test coverage |
| Data contract approval | PASS | Approved with explicit REVIEW conditions |
| UI safe rendering | PASS | Live service integration and REVIEW-aware rendering tests |
| Navigation integration | PASS | App route and existing-page integration test |
| Full regression | PASS | 614/614 TradeLab Pro tests |
| Yahoo adapter regression | PASS | 56/56 tests |
| Live NSE UDiFF ingestion | PASS | Official archive download, raw ISO header and timestamp validation |
| Live MII identity/coverage | REVIEW | Exceptions excluded; 99.2759% coverage |
| Final evidence register | PASS | Official schema evidence and live audit artifact |

A live data REVIEW is not converted to PASS. The implementation
passes because it identifies, reports and excludes unverified
observations instead of fabricating membership or unchanged counts.

## 5. Live Data Review Conditions

Live observation date: 2026-11-13  
Source: Official NSE CM UDiFF final Bhavcopy  
Normalized NSE CM STK EQ rows: 2,744  
Same-date eligible NSE MII universe: 2,762  
Exactly reconciled observations: 2,742  
Verified membership coverage: 99.2759%

Identity exceptions:

1. `DCMFINSERV` — raw MII identifies the EQ security, but
   Normal Market Eligibility is 0 and Auction Market Eligibility
   is 1. It is excluded from Normal-Market breadth.
2. `BNAGROCHEM` — UDiFF EQ row ISIN is
   `INE00HZ01011`; same-date MII EQ row ISIN is
   `INE00HZ01029`. No identifier is substituted; the row is
   excluded pending authoritative NSE resolution.
3. 20 MII members have no matching daily Bhavcopy observation.
   They are missing, not unchanged.

Live audit:
https://github.com/formarketon-lang/123/actions/runs/43550260364

Official schema evidence:
https://github.com/formarketon-lang/123/actions/runs/43550149037

The official UDiFF workbook and sample ZIP hashes, sheet name,
sample member and exact field/tag checks are recorded in:

`docs/evidence/nse_udiff_cm_bhavcopy_schema.md`

## 6. Non-Negotiable Scope

- NSE is primary; Yahoo Finance is secondary fallback.
- Source, fallback reason, fetch timestamp and raw archive hash
  must be preserved.
- Unverified Symbol/ISIN/Instrument ID rows are excluded.
- Missing observations are never treated as unchanged.
- No fake market data.
- No fabricated market signals.
- No unsupported sector mappings.
- BSE remains disabled.
- Sector Mapping Expansion remains OFF.
- No F&O Scanner.

## 7. Remaining Operational Review

These are ongoing data-quality controls, not Chapter 01
implementation blockers:

1. Resolve the BNAGROCHEM ISIN mismatch only with authoritative
   NSE evidence; until then, keep the row excluded.
2. Preserve DCMFINSERV's Normal-Market exclusion unless NSE
   eligibility changes in a verified MII snapshot.
3. Keep daily membership coverage at REVIEW whenever any
   expected MII member lacks an observation.
4. Re-run regression and live verification after future changes.

No automatic substitution, manual override or sector approval
is authorized by this acceptance.

## 8. Final Acceptance

All mandatory Chapter 01 implementation, service, schema,
provenance, UI, navigation and regression gates have verified
evidence. The current live breadth dataset remains REVIEW and
is displayed as such.

**CH01 STATUS: ACCEPTED WITH REVIEW CONDITIONS**  
**CH02 STATUS: NOT STARTED**

This acceptance applies only to Track B — TLP-MIM-001.
It does not mark Track A — TLP-MASTER-001 complete.

End of Chapter 01 Acceptance Register.
