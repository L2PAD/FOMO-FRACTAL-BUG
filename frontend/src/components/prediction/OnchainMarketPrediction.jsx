/**
 * OnchainMarketPrediction.jsx
 * ===========================
 * V2 On-chain Market Prediction — dark/light alternating blocks.
 * Compact 2-column grid layout, minimal whitespace.
 * Includes alt signals table (Strong BUYs / SELLs) at bottom.
 *
 * Data source: GET /api/prediction/onchain-market
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Shield, Zap,
  ArrowUpRight, ArrowDownRight, Minus, Brain, Radio,
  BarChart3, AlertTriangle, Wallet, Droplets, Cpu, Signal, Activity,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

/* ── Shared ────────────────────────────────────── */
const STATE_COLORS = {
  BULLISH: 'text-emerald-400', BEARISH: 'text-red-400', NEUTRAL: 'text-gray-400',
  STRONG: 'text-emerald-400', WEAK: 'text-red-400', ROTATION: 'text-amber-400',
  BUY: 'text-emerald-400', SELL: 'text-red-400', RANGE: 'text-amber-400',
};
const STATE_COLORS_LIGHT = {
  BULLISH: 'text-emerald-600', BEARISH: 'text-red-600', NEUTRAL: 'text-gray-500',
  STRONG: 'text-emerald-600', WEAK: 'text-red-600', ROTATION: 'text-amber-600',
  BUY: 'text-emerald-600', SELL: 'text-red-600', RANGE: 'text-amber-600',
};
const RISK_COLORS = { LOW: 'text-emerald-400', MODERATE: 'text-amber-400', ELEVATED: 'text-orange-400', HIGH: 'text-red-400' };
const RISK_COLORS_LIGHT = { LOW: 'text-emerald-700', MODERATE: 'text-amber-700', ELEVATED: 'text-orange-700', HIGH: 'text-red-700' };
const DIR_ICON_DARK = {
  up: <ArrowUpRight className="w-3 h-3 text-emerald-400" />,
  down: <ArrowDownRight className="w-3 h-3 text-red-400" />,
  neutral: <Minus className="w-3 h-3 text-gray-500" />,
};
const DIR_ICON_LIGHT = {
  up: <ArrowUpRight className="w-3 h-3 text-emerald-600" />,
  down: <ArrowDownRight className="w-3 h-3 text-red-600" />,
  neutral: <Minus className="w-3 h-3 text-gray-400" />,
};

/* ── Wrappers ──────────────────────────────────── */
function DarkBlock({ children, testId, className = '' }) {
  return <div className={`bg-[#080c12] rounded-xl border border-gray-800/40 px-4 py-3 ${className}`} data-testid={testId}>{children}</div>;
}
function LightBlock({ children, testId, className = '' }) {
  return <div className={`bg-white rounded-xl border border-gray-200 px-4 py-3 ${className}`} data-testid={testId}>{children}</div>;
}

/* ═══════ Block 1: Header (dark, full-width) ═══════ */
function HeaderBlock({ h }) {
  if (!h) return null;
  return (
    <DarkBlock testId="pred-header" className="!px-5 !py-4">
      <div className="flex items-start justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Radio className="w-3.5 h-3.5 text-cyan-500" />
            <span className="text-[9px] font-bold text-gray-600 uppercase tracking-[0.2em]">Market Prediction</span>
          </div>
          <div className="flex items-center gap-3 mb-2">
            <span className={`text-xl font-black tracking-tight ${STATE_COLORS[h.market_state] || 'text-white'}`}>{h.market_state}</span>
          </div>
          <div className="flex items-center gap-5">
            <div><p className="text-[8px] text-gray-600 uppercase">Altcoins</p><p className={`text-xs font-bold ${STATE_COLORS[h.altcoins_state] || 'text-gray-300'}`}>{h.altcoins_state}</p></div>
            <div><p className="text-[8px] text-gray-600 uppercase">Bias</p><p className={`text-xs font-bold ${STATE_COLORS[h.bias] || 'text-gray-300'}`}>{h.bias}</p></div>
            <div><p className="text-[8px] text-gray-600 uppercase">Confidence</p><p className="text-xs font-bold text-white tabular-nums">{h.confidence}%</p></div>
            <div><p className="text-[8px] text-gray-600 uppercase">Horizon</p><p className="text-xs font-bold text-gray-300">{h.horizon}</p></div>
          </div>
        </div>
        <div className="shrink-0 text-right space-y-1">
          <p className="text-[8px] text-gray-600 uppercase tracking-wider">Expected Move</p>
          {Object.entries(h.expected_moves || {}).map(([asset, move]) => (
            <div key={asset} className="flex items-center justify-end gap-2">
              <span className="text-[10px] text-gray-500">{asset}:</span>
              <span className={`text-sm font-bold tabular-nums ${String(move).startsWith('+') ? 'text-emerald-400' : String(move).startsWith('-') ? 'text-red-400' : 'text-gray-300'}`}>{move}</span>
            </div>
          ))}
          <div className="flex items-center justify-end gap-2 pt-1 border-t border-gray-800/30">
            <span className="text-[9px] text-gray-600">Risk</span>
            <span className={`text-[10px] font-bold ${RISK_COLORS[h.risk_level] || 'text-gray-400'}`}>{h.risk_level}</span>
          </div>
        </div>
      </div>
    </DarkBlock>
  );
}

/* ═══════ Block 2: Altcoins Direction (light, compact) ═══════ */
function AltDirectionBlock({ data }) {
  if (!data) return null;
  return (
    <LightBlock testId="pred-alt-direction">
      <div className="flex items-center gap-2 mb-2">
        <BarChart3 className="w-3.5 h-3.5 text-cyan-600" />
        <span className="text-[9px] font-bold text-gray-500 uppercase tracking-[0.15em]">Altcoins Direction</span>
        <span className="text-[9px] text-gray-400 ml-auto">{data.total_tokens} tracked</span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="flex items-center gap-1 mb-1">
            <TrendingUp className="w-3 h-3 text-emerald-500" />
            <span className="text-[8px] font-bold text-emerald-600 uppercase">Gainers</span>
          </div>
          <div className="space-y-0.5">
            {data.gainers?.length > 0 ? data.gainers.map((t, i) => (
              <div key={t.symbol} className="flex items-center gap-1 py-0.5" data-testid={`gainer-${i}`}>
                <span className="text-[10px] text-gray-400 w-3 tabular-nums">{i+1}</span>
                <span className="text-xs font-bold text-gray-900 flex-1">{t.symbol}</span>
                <span className="text-xs font-bold text-emerald-600 tabular-nums">{t.expected_move}</span>
              </div>
            )) : <p className="text-[10px] text-gray-400 italic">No gainers</p>}
          </div>
        </div>
        <div>
          <div className="flex items-center gap-1 mb-1">
            <TrendingDown className="w-3 h-3 text-red-500" />
            <span className="text-[8px] font-bold text-red-600 uppercase">Losers</span>
          </div>
          <div className="space-y-0.5">
            {data.losers?.length > 0 ? data.losers.map((t, i) => (
              <div key={t.symbol} className="flex items-center gap-1 py-0.5" data-testid={`loser-${i}`}>
                <span className="text-[10px] text-gray-400 w-3 tabular-nums">{i+1}</span>
                <span className="text-xs font-bold text-gray-900 flex-1">{t.symbol}</span>
                <span className="text-xs font-bold text-red-600 tabular-nums">{t.expected_move}</span>
              </div>
            )) : <p className="text-[10px] text-gray-400 italic">No losers</p>}
          </div>
        </div>
      </div>
    </LightBlock>
  );
}

/* ═══════ Block 3: Market Regime & Risk (light, compact) ═══════ */
function RegimeBlock({ r }) {
  if (!r) return null;
  return (
    <LightBlock testId="pred-regime">
      <div className="flex items-center gap-2 mb-2">
        <Shield className="w-3.5 h-3.5 text-amber-500" />
        <span className="text-[9px] font-bold text-gray-500 uppercase tracking-[0.15em]">Regime & Risk</span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div><p className="text-[8px] text-gray-400 uppercase">Regime</p><p className="text-sm font-bold text-gray-900">{r.regime}</p></div>
        <div><p className="text-[8px] text-gray-400 uppercase">Risk Mode</p><p className={`text-sm font-bold ${r.risk_mode === 'Risk ON' ? 'text-emerald-600' : 'text-red-600'}`}>{r.risk_mode}</p></div>
        <div><p className="text-[8px] text-gray-400 uppercase">Volatility</p><p className={`text-sm font-bold ${r.volatility === 'Low' ? 'text-emerald-600' : r.volatility === 'High' ? 'text-red-600' : 'text-amber-600'}`}>{r.volatility}</p></div>
        <div><p className="text-[8px] text-gray-400 uppercase">Liquidity</p><p className={`text-sm font-bold ${r.liquidity_state === 'Expanding' ? 'text-emerald-600' : r.liquidity_state === 'Contracting' ? 'text-red-600' : 'text-gray-600'}`}>{r.liquidity_state}</p></div>
      </div>
    </LightBlock>
  );
}

/* ═══════ Block 4: AI Market Narrative (dark, compact) ═══════ */
function NarrativeBlock({ text }) {
  if (!text) return null;
  return (
    <DarkBlock testId="pred-narrative">
      <div className="flex items-center gap-2 mb-1.5">
        <Brain className="w-3.5 h-3.5 text-violet-400" />
        <span className="text-[9px] font-bold text-gray-600 uppercase tracking-[0.15em]">AI Narrative</span>
      </div>
      <p className="text-[12px] text-gray-300 leading-relaxed">{text}</p>
    </DarkBlock>
  );
}

/* ═══════ Block 5: Model State (dark, compact) ═══════ */
function ModelStateBlock({ ms }) {
  if (!ms) return null;
  const qc = ms.data_quality === 'GOOD' ? 'text-emerald-400' : ms.data_quality === 'LIMITED' ? 'text-red-400' : 'text-amber-400';
  const sc = ms.signal_strength === 'HIGH' ? 'text-emerald-400' : ms.signal_strength === 'LOW' ? 'text-red-400' : 'text-amber-400';
  return (
    <DarkBlock testId="pred-model-state">
      <div className="flex items-center gap-2 mb-1.5">
        <Cpu className="w-3.5 h-3.5 text-gray-400" />
        <span className="text-[9px] font-bold text-gray-600 uppercase tracking-[0.15em]">Model State</span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-2">
        <div><p className="text-[8px] text-gray-600 uppercase">Confidence</p><p className="text-lg font-black text-white tabular-nums">{ms.confidence}%</p></div>
        <div><p className="text-[8px] text-gray-600 uppercase">Data Quality</p><p className={`text-sm font-bold ${qc}`}>{ms.data_quality}</p></div>
        <div><p className="text-[8px] text-gray-600 uppercase">Coverage</p><p className="text-xs font-bold text-gray-300 tabular-nums">{ms.coverage_entities} ent · {ms.coverage_clusters} cl</p></div>
        <div><p className="text-[8px] text-gray-600 uppercase">Signal</p><p className={`text-sm font-bold ${sc}`}>{ms.signal_strength}</p></div>
      </div>
      {ms.warning && (
        <div className="mt-2 pt-2 border-t border-gray-800/30 flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3 text-amber-400" />
          <span className="text-[10px] text-amber-400">{ms.warning}</span>
        </div>
      )}
    </DarkBlock>
  );
}

/* ═══════ Block 6: Prediction Drivers (light) ═══════ */
function DriversBlock({ drivers }) {
  if (!drivers?.length) return null;
  return (
    <LightBlock testId="pred-drivers">
      <div className="flex items-center gap-2 mb-2">
        <Zap className="w-3.5 h-3.5 text-cyan-600" />
        <span className="text-[9px] font-bold text-gray-500 uppercase tracking-[0.15em]">Prediction Drivers</span>
      </div>
      <div className="space-y-1">
        {drivers.map((d, i) => (
          <div key={i} className="flex items-center gap-2 py-1 px-2 rounded bg-gray-50 border border-gray-100" data-testid={`driver-${i}`}>
            {DIR_ICON_LIGHT[d.direction] || DIR_ICON_LIGHT.neutral}
            <span className="text-xs font-bold text-gray-900 w-24">{d.name}</span>
            <span className={`text-[10px] font-bold flex-1 ${d.direction === 'up' ? 'text-emerald-600' : d.direction === 'down' ? 'text-red-600' : 'text-gray-500'}`}>
              {d.signal} {d.direction === 'up' ? '\u2191' : d.direction === 'down' ? '\u2193' : ''}
            </span>
            <span className="text-[10px] text-gray-400 tabular-nums">{d.strength}%</span>
            <span className="text-[10px] text-gray-400 tabular-nums">{d.confidence}%</span>
          </div>
        ))}
      </div>
    </LightBlock>
  );
}

/* ═══════ Block 7: Smart Money (light) ═══════ */
function SmartMoneyBlock({ sm }) {
  if (!sm) return null;
  return (
    <LightBlock testId="pred-smart-money">
      <div className="flex items-center gap-2 mb-2">
        <Wallet className="w-3.5 h-3.5 text-violet-500" />
        <span className="text-[9px] font-bold text-gray-500 uppercase tracking-[0.15em]">Smart Money</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div><p className="text-[8px] text-gray-400 uppercase">Net Flow</p><p className={`text-base font-black tabular-nums ${sm.net_flow_raw >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{sm.net_flow}</p></div>
        <div><p className="text-[8px] text-gray-400 uppercase">Clusters</p><p className="text-base font-black text-gray-900 tabular-nums">{sm.active_clusters}</p></div>
        <div><p className="text-[8px] text-gray-400 uppercase">Conviction</p><p className="text-base font-black text-gray-900 tabular-nums">{sm.conviction}%</p></div>
      </div>
      <div className="flex items-center gap-4 mt-2 pt-2 border-t border-gray-100">
        <div><p className="text-[8px] text-gray-400 uppercase">Accum</p><p className={`text-xs font-bold ${sm.accumulation === 'HIGH' ? 'text-emerald-600' : sm.accumulation === 'LOW' ? 'text-red-600' : 'text-amber-600'}`}>{sm.accumulation}</p></div>
        <div><p className="text-[8px] text-gray-400 uppercase">Distrib</p><p className={`text-xs font-bold ${sm.distribution === 'HIGH' ? 'text-red-600' : sm.distribution === 'LOW' ? 'text-emerald-600' : 'text-amber-600'}`}>{sm.distribution}</p></div>
        {sm.rotation && <div><p className="text-[8px] text-gray-400 uppercase">Rotation</p><p className="text-xs font-bold text-cyan-600">{sm.rotation}</p></div>}
      </div>
    </LightBlock>
  );
}

/* ═══════ Block 8: Liquidity (dark) ═══════ */
function LiquidityBlock({ liq }) {
  if (!liq) return null;
  return (
    <DarkBlock testId="pred-liquidity">
      <div className="flex items-center gap-2 mb-2">
        <Droplets className="w-3.5 h-3.5 text-blue-400" />
        <span className="text-[9px] font-bold text-gray-600 uppercase tracking-[0.15em]">Liquidity & Flows</span>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div>
          <p className="text-[8px] text-gray-600 uppercase">Exchange Net</p>
          <p className={`text-base font-black tabular-nums ${liq.flow_type === 'outflow' ? 'text-emerald-400' : liq.flow_type === 'inflow' ? 'text-red-400' : 'text-gray-300'}`}>${liq.exchange_net_flow_fmt}</p>
          <p className="text-[8px] text-gray-600">({liq.flow_type})</p>
        </div>
        <div>
          <p className="text-[8px] text-gray-600 uppercase">Stablecoin</p>
          <p className={`text-base font-black tabular-nums ${liq.stablecoin_net >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>${liq.stablecoin_net_fmt}</p>
        </div>
        <div>
          <p className="text-[8px] text-gray-600 uppercase">Inventory</p>
          <p className="text-sm font-bold text-gray-300">{liq.inventory_state}</p>
        </div>
      </div>
      {liq.liquidity_shock && liq.liquidity_shock !== 'None' && (
        <div className="mt-2 pt-2 border-t border-gray-800/30 flex items-center gap-1.5">
          <AlertTriangle className="w-3 h-3 text-amber-400" />
          <span className="text-[10px] text-amber-400">Shock: {liq.liquidity_shock}</span>
        </div>
      )}
    </DarkBlock>
  );
}

/* ═══════ Block 9: Signals Feed (dark) ═══════ */
function SignalsFeedBlock({ signals }) {
  if (!signals?.length) return null;
  return (
    <DarkBlock testId="pred-signals">
      <div className="flex items-center gap-2 mb-2">
        <Signal className="w-3.5 h-3.5 text-cyan-400" />
        <span className="text-[9px] font-bold text-gray-600 uppercase tracking-[0.15em]">Top Signals</span>
        <span className="text-[9px] text-gray-600 ml-auto">{signals.length}</span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {signals.map((s, i) => (
          <div key={i} className="flex items-center gap-1.5 px-2 py-1.5 rounded bg-white/[0.03] border border-gray-800/20" data-testid={`signal-${i}`}>
            {DIR_ICON_DARK[s.direction] || DIR_ICON_DARK.neutral}
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-bold text-white truncate">{s.type}</p>
              {s.entity && <p className="text-[8px] text-gray-600 truncate">{s.entity}</p>}
            </div>
            {s.confidence > 0 && <span className="text-[9px] text-gray-500 tabular-nums shrink-0">{s.confidence}%</span>}
          </div>
        ))}
      </div>
    </DarkBlock>
  );
}

/* ═══════ Block 10: Alt Signals Table (white, Exchange-style) ═══════ */
function AltSignalsTable({ alts }) {
  if (!alts) return null;
  const buys = alts.gainers || [];
  const sells = alts.losers || [];
  const hasSells = sells.length > 0;
  const hasBuys = buys.length > 0;
  const maxRows = Math.max(buys.length, sells.length);
  if (!maxRows) return null;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="pred-alt-signals-table">
      <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between">
        <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">On-chain Alt Signals</div>
        <span className="text-xs text-gray-400">{buys.length + sells.length} assets</span>
      </div>
      <table className="w-full text-[13px]">
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
            <th colSpan={4} className="text-left px-4 py-2 text-xs font-medium text-emerald-700" style={{ background: 'rgba(16,185,129,0.06)' }}>Strong BUYs</th>
            {hasSells && <th colSpan={4} className="text-left px-4 py-2 text-xs font-medium text-red-700" style={{ background: 'rgba(239,68,68,0.05)' }}>Strong SELLs</th>}
          </tr>
          <tr style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
            <th className="text-left py-1.5 px-4 font-medium text-[11px] text-gray-400 uppercase">Symbol</th>
            <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Conf</th>
            <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Move</th>
            <th className="text-center py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Risk</th>
            {hasSells && <>
              <th className="text-left py-1.5 px-4 font-medium text-[11px] text-gray-400 uppercase">Symbol</th>
              <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Conf</th>
              <th className="text-right py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Move</th>
              <th className="text-center py-1.5 px-3 font-medium text-[11px] text-gray-400 uppercase">Risk</th>
            </>}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: maxRows }).map((_, i) => {
            const buy = buys[i];
            const sell = sells[i];
            return (
              <tr key={i} style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}>
                {buy ? <>
                  <td className="py-2 px-4">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900">{buy.symbol}</span>
                      <span className="text-[10px] font-bold text-emerald-600">BUY</span>
                    </div>
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums font-medium text-gray-700">{buy.confidence}%</td>
                  <td className="py-2 px-3 text-right tabular-nums font-medium text-emerald-600">{buy.expected_move}</td>
                  <td className="py-2 px-3 text-center">
                    <span className="text-[10px] font-semibold text-amber-700">HIGH</span>
                  </td>
                </> : <td colSpan={4}></td>}
                {hasSells && (sell ? <>
                  <td className="py-2 px-4">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900">{sell.symbol}</span>
                      <span className="text-[10px] font-bold text-red-600">SELL</span>
                    </div>
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums font-medium text-gray-700">{sell.confidence}%</td>
                  <td className="py-2 px-3 text-right tabular-nums font-medium text-red-600">{sell.expected_move}</td>
                  <td className="py-2 px-3 text-center">
                    <span className="text-[10px] font-semibold text-amber-700">HIGH</span>
                  </td>
                </> : <td colSpan={4}></td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
        <span className="text-[11px] text-gray-400">Derived from on-chain flows</span>
        <span className="text-[11px] text-gray-400">Click row to view chart</span>
      </div>
    </div>
  );
}

/* ═══════ Main Component ═══════ */
export default function OnchainMarketPrediction() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API}/api/prediction/onchain-market`);
      const json = await res.json();
      if (json.ok) { setData(json); setError(null); }
      else setError(json.error || 'Failed to load');
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(fetchData, 60000);
    return () => clearInterval(iv);
  }, [fetchData]);

  if (loading && !data) {
    return <div className="flex items-center justify-center h-64" data-testid="pred-loading"><div className="animate-spin w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full" /></div>;
  }
  if (error && !data) {
    return <div className="text-center py-12" data-testid="pred-error"><p className="text-sm text-red-400">{error}</p></div>;
  }
  if (!data) return null;

  return (
    <div className="space-y-3" data-testid="onchain-market-prediction">
      {/* Row 1: Header (dark, full width) */}
      <HeaderBlock h={data.header} />

      {/* Row 2: Altcoins Direction (light) + Regime (light) — 2 columns */}
      <div className="grid grid-cols-2 gap-3">
        <AltDirectionBlock data={data.alt_predictions} />
        <RegimeBlock r={data.regime} />
      </div>

      {/* Row 3: AI Narrative (dark) + Model State (dark) — 2 columns */}
      <div className="grid grid-cols-2 gap-3">
        <NarrativeBlock text={data.narrative} />
        <ModelStateBlock ms={data.model_state} />
      </div>

      {/* Row 4: Drivers (light) + Smart Money (light) — 2 columns */}
      <div className="grid grid-cols-2 gap-3">
        <DriversBlock drivers={data.drivers} />
        <SmartMoneyBlock sm={data.smart_money} />
      </div>

      {/* Row 5: Liquidity (dark) + Signals (dark) — 2 columns */}
      <div className="grid grid-cols-2 gap-3">
        <LiquidityBlock liq={data.liquidity} />
        <SignalsFeedBlock signals={data.signals} />
      </div>

      {/* Row 6: Alt Signals Table (white, full width) */}
      <AltSignalsTable alts={data.alt_predictions} />
    </div>
  );
}
