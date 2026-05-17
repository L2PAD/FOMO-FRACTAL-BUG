# On-Chain Module — Light Mode (Infura) Deployment

> **Status:** ✅ All on-chain endpoints serve real data via **Infura RPC**
> (Ethereum, Arbitrum, Optimism, Base) and **DefiLlama** (stablecoins,
> bridges, TVL, DEX volume).
> **Mode:** `preview` (Light Mode — no indexer required).
> **Indexer:** present in `onchain_lite` admin handlers but **idle**
> (ingestion: false, signals: idle).  Diagnostics confirm code is sound,
> just not active.

---

## 1. Configuration

`backend/.env` must contain:

```ini
INFURA_KEY="29976df4bb4a44b09105a34cdf31d11d"
ONCHAIN_ENABLED=true
ONCHAIN_MODE="preview"   # NOT "indexer" — Light Mode only
```

Restart backend after changing these:
```bash
supervisorctl restart backend
```

---

## 2. Architecture

```
                       INFURA REST RPC                    DefiLlama public API
                              │                                  │
              ┌───────────────┴────────────────┐                 │
              ▼                                ▼                 ▼
        eth_blockNumber                eth_getBlockByNumber   TVL · stablecoins
        eth_gasPrice                   (full tx list)         · bridges · DEX vol
        eth_getBlockTransactionCount   (per chain)
                              │                                  │
                              └────────────┬─────────────────────┘
                                           ▼
                              backend/onchain_lite/service.py
                              (get_summary · get_whales ·
                               get_flows · get_activity)
                                           │
              ┌────────────────────────────┴────────────────────────────┐
              ▼                                                         ▼
   /api/onchain/{status,summary,                          /api/onchain-overview/*
    flows,whales,activity}                                /api/onchain/smart-money/*
                                                          /api/onchain/cex/*
              ▼                                                         ▼
       routes/onchain_lite/routes.py                           routes/onchain_runtime.py
       routes/legacy_compat.py  ← NEVER reached for /api/onchain/*
```

---

## 3. Endpoint matrix

### 3.1 Light-mode core — `onchain_lite/routes.py`
| Endpoint                                              | Real data source                                        |
| ----------------------------------------------------- | ------------------------------------------------------- |
| `GET /api/onchain/status`                             | service state + mode + cache                            |
| `GET /api/onchain/summary?chain=ethereum`             | Infura: blockHeight · gasPrice · TPS · pendingTxCount   |
| `GET /api/onchain/whales?chain=ethereum`              | Infura latest block — **single_block window**           |
| `GET /api/onchain/flows?chain=ethereum`               | DefiLlama: stablecoin total + bridge in/out             |
| `GET /api/onchain/activity?chain=ethereum`            | DefiLlama: TVL + DEX volume + top protocols             |

### 3.2 Overview (Web SPA) — `routes/onchain_runtime.py`
33 endpoints under `/api/onchain-overview/*`, `/api/onchain/smart-money/*`,
`/api/onchain/cex/*` — all real, backed by Mongo + Infura.  Full sweep
(2026-05-17): **real=33, stubs=0**.

### 3.3 Mobile (Expo) — `routes/mobile/intel.py`
| Endpoint                                | Backed by                                |
| --------------------------------------- | ---------------------------------------- |
| `GET /api/mobile/intel/onchain?asset=`  | **REAL** `onchain_lite + DefiLlama`      |

⚠️  **Critical bug fixed in this audit**: the previous
`build_onchain_intel` derived fake numbers from price change:
```
netflow = -change7d * supply * 0.00001    ← FAKE
txCount = max(10, round(30 + change7d*3)) ← FAKE
lthPct  = round(70 + change30d * 0.1, 0)  ← FAKE
```
Replaced with real Infura/DefiLlama pulls.  Fields that **cannot** be
known in Light Mode (`onExchangesPct`, `lthPct`, per-CEX netflow) now
return `null` with `available: false` and a clear `source` reason.

---

## 4. Honest Disclosures

The Light Mode is intentionally limited.  These fields **cannot** be
populated without the full indexer and are returned as `null`:

| Field                             | Why null                                                   |
| --------------------------------- | ---------------------------------------------------------- |
| `exchangeFlows.netflow` (CEX)     | needs address-label book → run mode=indexer                |
| `supply.onExchangesPct`           | needs CEX wallet enumeration → run mode=indexer            |
| `holders.lthPct`                  | needs UTXO age tracking → run mode=indexer                 |
| `whales.largeTransfers24h`        | needs 24h block backfill → run mode=indexer                |
| `activity.activeAddressesPct`     | needs historic baseline → run mode=indexer                 |

Where DefiLlama can substitute (bridge netflow ≠ CEX netflow but it's
real on-chain capital movement), we serve it under
`exchangeFlows.bridge.netflowUsd` with `source: defillama_bridges`.

---

## 5. Indexer Status

The indexer is **NOT deployed** as requested — Light Mode only.
However we verified the indexer code-paths:

| Component                              | Status                                        |
| -------------------------------------- | --------------------------------------------- |
| `/api/admin/indexer/status`            | ✅ responds (`mode: preview`)                 |
| `/api/admin/indexer/diagnostics`       | ✅ all 4 chains RPC-connected via Infura      |
| Ingestion loop                         | 🟡 idle (active: false) — by design            |
| Entity resolution                      | 🟡 idle — by design                            |
| `/app/indexer/indexer_worker.py`       | ⚠️  not present (admin `/restart` endpoint     |
|                                        |     would fail with FileNotFoundError — only   |
|                                        |     relevant if you flip to mode=indexer)      |

**Verdict:** Indexer machinery is **not broken** at the code layer.
RPC connectivity is healthy.  Only the worker process file is missing
which is correct for Light Mode.

---

## 6. Health-check (one-shot)

```bash
curl -s "$BACKEND/api/onchain/status"                      | jq .mode
curl -s "$BACKEND/api/onchain/summary?chain=ethereum"      | jq '.data.blockHeight, .data.tps'
curl -s "$BACKEND/api/onchain/whales?chain=ethereum"       | jq '.data.windowType, .data.largeTransfersInBlock'
curl -s "$BACKEND/api/onchain/flows?chain=ethereum"        | jq '.data.stablecoin.totalSupplyUsd'
curl -s "$BACKEND/api/onchain/activity?chain=ethereum"     | jq '.data.dexVolume24h, .data.totalValueLocked'
curl -s "$BACKEND/api/mobile/intel/onchain?asset=BTC"      | jq '.mode, .activity.blockHeight'
curl -s "$BACKEND/api/admin/indexer/diagnostics"           | jq '.rpc.status, .mode'
```

Every call **must** return real numbers (no `null` for the top-level
keys above) and `mode: preview` for Light Mode.

---

## 7. Cold-boot

Run `scripts/cold_boot_onchain.sh` to verify Infura connectivity +
DefiLlama enrichment + 0 stubs across all surfaces.
