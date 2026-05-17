/**
 * HypothesesView.jsx — Strategy Lab v2
 * ════════════════════════════════════════════════════════════════════════════
 *
 * ANALYTICAL LAYER ONLY:
 *   "Что РАБОТАЕТ на истории?" — backtest engine harness.
 *   NO live trading. NO execution. NO direction signals for "now".
 *   Hypotheses → answer "does this strategy have edge?"
 *   Trading layer (ORCH/Meta/FinalGate) consumes our metrics separately.
 *
 * Layout:
 *   ┌─ Top Stats Bar ──────────────────────────────┐
 *   │  6 strategies · last run · best PF · avg WR  │
 *   ├─ Backtest Bench (Symbol / TF / Run All) ─────┤
 *   ├─ Results Leaderboard (sortable table) ───────┤
 *   ├─ Strategy Cards Grid (one per hypothesis) ──┤
 *   │   [conditions list] [last run metrics]       │
 *   │   [▶ Run Backtest]  [📊 History]             │
 *   └───────────────────────────────────────────────┘
 *
 * No Saved Ideas, no alignments, no fake numbers.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import styled, { css, keyframes } from 'styled-components';
import {
  Beaker, RefreshCw, Play, History, Loader2, ChevronDown, ChevronUp,
  TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle2,
  ArrowUpDown, X, Activity, BarChart3,
} from 'lucide-react';
import { useMarket } from '../../../store/marketStore';

const API = process.env.REACT_APP_BACKEND_URL || '';

/* ════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ════════════════════════════════════════════════════════════ */
const T = {
  bg:        '#f6f7fb',
  surface:   '#ffffff',
  surface2:  '#f9fafc',
  border:    '#e6eaf2',
  borderHi:  '#d2d9e7',
  text:      '#0f172a',
  text2:     '#475569',
  text3:     '#94a3b8',
  primary:   '#3b82f6',
  primaryBg: 'rgba(59,130,246,0.08)',
  green:     '#16a34a',
  greenBg:   'rgba(34,197,94,0.10)',
  red:       '#dc2626',
  redBg:     'rgba(239,68,68,0.10)',
  amber:     '#d97706',
  amberBg:   'rgba(217,119,6,0.10)',
  purple:    '#7c3aed',
  purpleBg:  'rgba(124,58,237,0.10)',
};

const spin = keyframes`from { transform: rotate(0); } to { transform: rotate(360deg); }`;

const Spinner = styled(Loader2)`
  animation: ${spin} 1s linear infinite;
  color: ${({ $color }) => $color || T.primary};
`;

/* ════════════════════════════════════════════════════════════
   LAYOUT
   ════════════════════════════════════════════════════════════ */
const Container = styled.div`
  padding: 22px 26px 60px;
  background: ${T.bg};
  min-height: calc(100vh - 140px);
  box-sizing: border-box;
  overflow-x: hidden;
`;

const SectionHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 14px;
  flex-wrap: wrap;

  h3 {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: ${T.text};
    letter-spacing: -0.01em;
    display: inline-flex;
    align-items: center;
    gap: 8px;

    svg { color: ${T.primary}; }
    .count {
      background: ${T.surface2};
      color: ${T.text2};
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid ${T.border};
      font-size: 11px;
      letter-spacing: 0;
    }
  }
`;

/* ─── Top Stats Bar ─────────────────────────────────────── */
const StatsBar = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 22px;

  @media (max-width: 900px) { grid-template-columns: 1fr 1fr; }
`;

const StatTile = styled.div`
  background: ${T.surface};
  border: 1px solid ${T.border};
  border-radius: 12px;
  padding: 14px 16px;

  .label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: ${T.text3};
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
    svg { width: 12px; height: 12px; }
  }
  .value {
    font-size: 21px;
    font-weight: 700;
    color: ${T.text};
    letter-spacing: -0.015em;
    line-height: 1.1;
  }
  .sub {
    font-size: 11px;
    color: ${T.text3};
    margin-top: 4px;
  }
  &.green .value { color: ${T.green}; }
  &.amber .value { color: ${T.amber}; }
  &.red   .value { color: ${T.red}; }
`;

/* ─── Backtest Bench ────────────────────────────────────── */
const BenchCard = styled.div`
  background: ${T.surface};
  border: 1px solid ${T.border};
  border-radius: 14px;
  padding: 16px 20px;
  margin-bottom: 22px;

  .row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .field .label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: ${T.text3};
  }
`;

const Select = styled.select`
  height: 34px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid ${T.border};
  background: ${T.surface};
  color: ${T.text};
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  outline: none;
  transition: border-color 0.12s;
  min-width: 120px;

  &:hover, &:focus { border-color: ${T.primary}; }
`;

const PrimaryBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid ${T.primary};
  background: ${T.primary};
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.12s;
  font-family: inherit;
  white-space: nowrap;

  svg { width: 14px; height: 14px; }
  &:hover:not(:disabled) { background: #2563eb; border-color: #2563eb; }
  &:disabled { opacity: 0.55; cursor: not-allowed; }
  &.spinning svg { animation: ${spin} 1s linear infinite; }
`;

const SecondaryBtn = styled(PrimaryBtn)`
  border: 1px solid ${T.border};
  background: ${T.surface};
  color: ${T.text2};
  &:hover:not(:disabled) {
    border-color: ${T.primary};
    color: ${T.primary};
    background: ${T.surface};
  }
`;

const GhostBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 11px;
  border-radius: 8px;
  border: 1px solid ${T.border};
  background: ${T.surface};
  color: ${T.text2};
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.12s;
  font-family: inherit;

  svg { width: 13px; height: 13px; }
  &:hover:not(:disabled) { border-color: ${T.primary}; color: ${T.primary}; }
  &:disabled { opacity: 0.55; cursor: not-allowed; }
  &.spinning svg { animation: ${spin} 1s linear infinite; }
`;

/* ─── Leaderboard Table ─────────────────────────────────── */
const TableCard = styled.div`
  background: ${T.surface};
  border: 1px solid ${T.border};
  border-radius: 14px;
  padding: 0;
  overflow: hidden;
  margin-bottom: 22px;
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;

  thead th {
    text-align: left;
    padding: 12px 16px;
    background: ${T.surface2};
    color: ${T.text3};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-bottom: 1px solid ${T.border};
    cursor: ${({ $sortable }) => ($sortable === false ? 'default' : 'pointer')};
    user-select: none;
    white-space: nowrap;

    .ic { display: inline-flex; align-items: center; gap: 5px; }
    svg { width: 10px; height: 10px; opacity: 0.5; }
  }
  thead th:hover svg { opacity: 1; color: ${T.primary}; }

  tbody td {
    padding: 13px 16px;
    border-bottom: 1px solid ${T.border};
    color: ${T.text};
    font-weight: 600;
    vertical-align: middle;
  }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr:hover { background: ${T.surface2}; }

  td.dim   { color: ${T.text3}; font-weight: 500; }
  td.green { color: ${T.green}; }
  td.red   { color: ${T.red}; }
  td.amber { color: ${T.amber}; }

  .name {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .strat-name {
    color: ${T.text};
    font-weight: 700;
  }
  .strat-meta {
    font-size: 11px;
    color: ${T.text3};
    font-weight: 500;
  }
`;

const CategoryChip = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.05em;
  background: ${T.surface2};
  color: ${T.text2};
  border: 1px solid ${T.border};
  text-transform: uppercase;
`;

const VerdictPill = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;

  svg { width: 11px; height: 11px; }

  ${({ $verdict }) => {
    if ($verdict === 'VALID') return css`background: ${T.greenBg}; color: ${T.green};`;
    if ($verdict === 'WEAK')  return css`background: ${T.amberBg}; color: ${T.amber};`;
    if ($verdict === 'INVALID') return css`background: ${T.redBg}; color: ${T.red};`;
    return css`background: ${T.surface2}; color: ${T.text3}; border: 1px solid ${T.border};`;
  }}
`;

/* ─── Strategy Cards Grid ───────────────────────────────── */
const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;

  @media (max-width: 1100px) { grid-template-columns: 1fr; }
`;

const Card = styled.article`
  background: ${T.surface};
  border: 1px solid ${T.border};
  border-radius: 14px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: border-color 0.15s, box-shadow 0.15s;
  min-width: 0;

  &:hover {
    border-color: ${T.borderHi};
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
  }
`;

const CardHead = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;

  .name {
    font-size: 15px;
    font-weight: 700;
    color: ${T.text};
    letter-spacing: -0.01em;
    line-height: 1.25;
    margin: 0 0 4px 0;
  }
  .desc {
    font-size: 12px;
    color: ${T.text3};
    line-height: 1.45;
  }
`;

const CardChips = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
`;

const SmallChip = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 700;
  background: ${T.surface2};
  color: ${T.text2};
  border: 1px solid ${T.border};
  text-transform: uppercase;
  letter-spacing: 0.04em;

  svg { width: 11px; height: 11px; }
`;

const DirChip = styled(SmallChip)`
  ${({ $dir }) => {
    if ($dir === 'LONG')  return css`background: ${T.greenBg}; color: ${T.green}; border-color: rgba(34,197,94,0.3);`;
    if ($dir === 'SHORT') return css`background: ${T.redBg};  color: ${T.red};   border-color: rgba(239,68,68,0.3);`;
    return css`background: ${T.surface2}; color: ${T.text2};`;
  }}
`;

const Conditions = styled.div`
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: ${T.surface2};
  border-radius: 10px;
  padding: 11px 12px;

  .head {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
    color: ${T.text3};
    text-transform: uppercase;
    margin-bottom: 3px;
  }
`;

const Cond = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  font-size: 12px;
  line-height: 1.35;

  .indicator {
    color: ${T.text};
    font-weight: 600;
  }
  .op {
    color: ${T.text3};
    font-size: 11px;
    font-weight: 600;
    margin: 0 4px;
  }
  .val {
    color: ${T.primary};
    font-family: 'SF Mono', ui-monospace, monospace;
    font-weight: 700;
    white-space: nowrap;
  }
  .weight {
    font-size: 10px;
    color: ${T.text3};
    font-weight: 600;
    background: ${T.surface};
    padding: 1px 6px;
    border-radius: 4px;
    border: 1px solid ${T.border};
    margin-left: auto;
    flex-shrink: 0;
  }
`;

const KPIs = styled.div`
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
`;

const KPI = styled.div`
  background: ${T.surface2};
  border-radius: 8px;
  padding: 8px 10px;
  text-align: left;
  min-width: 0;

  .l {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: ${T.text3};
    text-transform: uppercase;
    margin-bottom: 3px;
  }
  .v {
    font-size: 13px;
    font-weight: 700;
    color: ${T.text};
    line-height: 1.1;
  }
  &.green .v { color: ${T.green}; }
  &.amber .v { color: ${T.amber}; }
  &.red   .v { color: ${T.red}; }
  &.dim   .v { color: ${T.text3}; }
`;

const Actions = styled.div`
  display: flex;
  gap: 8px;
  margin-top: auto;
`;

const RunningOverlay = styled.div`
  position: relative;
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.6);
    border-radius: 14px;
    pointer-events: none;
  }
`;

/* ─── History Drawer ───────────────────────────────────── */
const Drawer = styled.div`
  position: fixed;
  top: 0; right: 0; bottom: 0;
  width: 480px;
  max-width: 100%;
  background: ${T.surface};
  border-left: 1px solid ${T.border};
  box-shadow: -8px 0 32px rgba(15, 23, 42, 0.1);
  z-index: 50;
  display: flex;
  flex-direction: column;
  transform: translateX(${({ $open }) => ($open ? '0' : '100%')});
  transition: transform 0.3s ease;
`;

const DrawerHead = styled.div`
  padding: 18px 20px;
  border-bottom: 1px solid ${T.border};
  display: flex;
  align-items: center;
  justify-content: space-between;

  h4 {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    color: ${T.text};
  }
  .sub { font-size: 11px; color: ${T.text3}; margin-top: 2px; }

  button.close {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    border: 1px solid ${T.border};
    background: ${T.surface};
    color: ${T.text2};
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.12s;
    &:hover { border-color: ${T.red}; color: ${T.red}; }
    svg { width: 14px; height: 14px; }
  }
`;

const DrawerBody = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 60px;
`;

const Backdrop = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  z-index: 49;
  opacity: ${({ $open }) => ($open ? 1 : 0)};
  pointer-events: ${({ $open }) => ($open ? 'auto' : 'none')};
  transition: opacity 0.25s ease;
`;

const RunRow = styled.div`
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 10px;
  padding: 11px 12px;
  background: ${T.surface2};
  border: 1px solid ${T.border};
  border-radius: 10px;
  margin-bottom: 8px;
  font-size: 12px;

  .id {
    font-family: 'SF Mono', ui-monospace, monospace;
    font-size: 11px;
    color: ${T.primary};
    font-weight: 700;
  }
  .meta {
    color: ${T.text3};
    font-weight: 500;
    line-height: 1.5;
    span.k { color: ${T.text2}; font-weight: 600; }
  }
  .status {
    align-self: center;
    font-size: 10px;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 999px;
    text-transform: uppercase;
  }
  .status.COMPLETED { background: ${T.greenBg}; color: ${T.green}; }
  .status.FAILED    { background: ${T.redBg};   color: ${T.red}; }
  .status.RUNNING   { background: ${T.primaryBg}; color: ${T.primary}; }
`;

/* ─── Empty / Loading / Error ──────────────────────────── */
const StateBox = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  background: ${T.surface};
  border-radius: 14px;
  border: 1px dashed ${T.border};
  color: ${T.text2};

  svg { width: 32px; height: 32px; color: ${T.borderHi}; margin-bottom: 12px; }
  h4 { font-size: 15px; font-weight: 700; color: ${T.text}; margin: 0 0 6px 0; }
  p  { font-size: 13px; color: ${T.text2}; margin: 0; max-width: 400px; line-height: 1.5; }
`;

const ErrorBanner = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: ${T.redBg};
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 10px;
  margin-bottom: 16px;
  font-size: 13px;
  color: ${T.red};

  svg { width: 16px; height: 16px; flex-shrink: 0; }
`;

/* ════════════════════════════════════════════════════════════
   API HELPERS
   ════════════════════════════════════════════════════════════ */
async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

const API_HYPO = {
  list:   () => fetchJSON(`${API}/api/hypothesis/list`),
  top:    () => fetchJSON(`${API}/api/hypothesis/top?limit=20`),
  one:    (id) => fetchJSON(`${API}/api/hypothesis/${id}`),
  history:(id) => fetchJSON(`${API}/api/hypothesis/${id}/history`),
  results:(id) => fetchJSON(`${API}/api/hypothesis/${id}/results`),
  run:    (id, body) => fetchJSON(
    `${API}/api/hypothesis/run?hypothesis_id=${encodeURIComponent(id)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  ),
};

/* ════════════════════════════════════════════════════════════
   PERSISTENT RESULTS RESOLVER
   ════════════════════════════════════════════════════════════
   Backend stores every run-result. /results returns ALL historical
   runs for a hypothesis (sorted by computed_at desc). To rebuild the
   "last result for current symbol/tf" view we:
     1) Fetch /results once per hypothesis
     2) Pair them with /history to attach symbol/timeframe/sample_size
     3) Pick the most recent result that matches the chosen symbol+tf
   This makes the UI stateless across reloads — the DB IS the source.
   ════════════════════════════════════════════════════════════ */
async function fetchLatestForFilter(hypothesisId, symbol, timeframe) {
  try {
    // /history is fast (1 round-trip per id) — joins symbol/timeframe to runs.
    const [hist, res] = await Promise.all([
      API_HYPO.history(hypothesisId),
      API_HYPO.results(hypothesisId),
    ]);
    const runs = hist?.runs || [];
    const results = res?.results || [];
    // index runs by run_id for join
    const runIx = {};
    for (const r of runs) runIx[r.run_id] = r;
    // find latest result whose run matches symbol+tf
    const matched = results
      .map(r => ({ result: r, run: runIx[r.run_id] }))
      .filter(x =>
        x.run &&
        (!symbol || x.run.symbol === symbol) &&
        (!timeframe || (x.run.timeframe || '').toLowerCase() === timeframe.toLowerCase())
      )
      .sort((a, b) => (b.result.computed_at || '').localeCompare(a.result.computed_at || ''));
    if (!matched.length) return null;
    const top = matched[0];
    return joinRunResult(hypothesisId, top.run, top.result);
  } catch {
    return null;
  }
}

function joinRunResult(id, run, result) {
  return {
    hypothesis_id: id,
    run_id: result?.run_id || run?.run_id,
    symbol: run?.symbol,
    timeframe: run?.timeframe,
    sample_size: run?.sample_size,
    triggers_found: run?.triggers_found,
    win_rate: result?.win_rate,
    profit_factor: result?.profit_factor,
    expectancy: result?.expectancy,
    max_drawdown: result?.max_drawdown,
    avg_return: result?.avg_return,
    sharpe_ratio: result?.sharpe_ratio,
    sortino_ratio: result?.sortino_ratio,
    regime_breakdown: result?.regime_breakdown,
    verdict: result?.verdict,
    verdict_reason: result?.verdict_reason,
    confidence_score: result?.confidence_score,
    winning_trades: result?.winning_trades,
    losing_trades: result?.losing_trades,
    computed_at: result?.computed_at || run?.finished_at,
  };
}

/* ════════════════════════════════════════════════════════════
   FORMATTERS
   ════════════════════════════════════════════════════════════ */
const pct = (v, d = 1) => v == null ? '—' : `${(v * 100).toFixed(d)}%`;
const num = (v, d = 2) => v == null ? '—' : Number(v).toFixed(d);
const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return '—'; }
};
const verdictIcon = (v) => v === 'VALID' ? <CheckCircle2 /> : v === 'INVALID' ? <X /> : <AlertTriangle />;

const bestRegime = (rb) => {
  if (!rb) return null;
  let best = null;
  for (const [name, r] of Object.entries(rb)) {
    if (!best || r.win_rate > best.wr) best = { name, wr: r.win_rate, ret: r.avg_return };
  }
  return best;
};

const dirOf = (h) => (h.expected_outcome?.direction || h.direction || 'NEUTRAL').toUpperCase();
const tfsOf = (h) => h.applicable_timeframes || [];

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
const TIMEFRAMES = ['1h', '4h', '1d'];

/* ════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ════════════════════════════════════════════════════════════ */
const HypothesesView = () => {
  const market = useMarket();

  // strategies + their last results (joined)
  const [strategies, setStrategies] = useState([]);
  const [resultsMap, setResultsMap] = useState({});   // hypothesis_id → metrics
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // bench controls
  const [symbol, setSymbol] = useState(market?.symbol || 'BTCUSDT');
  const [tf, setTf] = useState((market?.timeframe || '4H').toLowerCase());

  // run state per hypothesis_id
  const [runningIds, setRunningIds] = useState(new Set());
  const [runAllInFlight, setRunAllInFlight] = useState(false);

  // sort
  const [sortBy, setSortBy] = useState('profit_factor');
  const [sortDir, setSortDir] = useState('desc');

  // history drawer
  const [historyFor, setHistoryFor] = useState(null);     // hypothesis object
  const [historyData, setHistoryData] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  /* ─── load registry + persisted results for current filter ──────── */
  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await API_HYPO.list();
      const strats = list?.hypotheses || [];
      setStrategies(strats);
      // Resolve last result per hypothesis for current symbol+tf — concurrently
      const entries = await Promise.all(
        strats.map(async (h) => [h.hypothesis_id, await fetchLatestForFilter(h.hypothesis_id, symbol, tf)])
      );
      const map = {};
      for (const [id, r] of entries) if (r) map[id] = r;
      setResultsMap(map);
    } catch (e) {
      console.error(e);
      setError(`Failed to load strategies: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [symbol, tf]);

  useEffect(() => { loadAll(); }, [loadAll]);

  /* ─── run a single backtest ─────────────────────────── */
  const runOne = useCallback(async (hypothesis, overrideSymbol, overrideTf) => {
    const id = hypothesis.hypothesis_id;
    const useSym = overrideSymbol || symbol;
    const useTf = overrideTf || tf;
    const key = overrideSymbol || overrideTf ? `${id}::${useSym}/${useTf}` : id;
    setRunningIds(prev => { const n = new Set(prev); n.add(key); return n; });
    try {
      const res = await API_HYPO.run(id, { symbol: useSym, timeframe: useTf });
      const run = res?.run || {};
      const result = res?.result || {};
      const merged = joinRunResult(id, { ...run, symbol: useSym, timeframe: useTf }, result);
      // Update only the main map if matches current filter
      if (useSym === symbol && useTf.toLowerCase() === tf.toLowerCase()) {
        setResultsMap(prev => ({ ...prev, [id]: merged }));
      }
      return merged;
    } catch (e) {
      console.error('run failed', e);
      setError(`Run failed for ${hypothesis.name}: ${e.message}`);
      return null;
    } finally {
      setRunningIds(prev => { const n = new Set(prev); n.delete(key); return n; });
    }
  }, [symbol, tf]);

  /* ─── run all sequentially (avoid backend overload) ── */
  const runAll = useCallback(async () => {
    if (runAllInFlight) return;
    setRunAllInFlight(true);
    setError(null);
    for (const h of strategies) {
      // Skip strategies that don't support this TF
      const tfsLower = (h.applicable_timeframes || []).map(s => s.toLowerCase());
      if (tfsLower.length > 0 && !tfsLower.includes(tf.toLowerCase())) continue;
      // eslint-disable-next-line no-await-in-loop
      await runOne(h);
    }
    setRunAllInFlight(false);
  }, [strategies, tf, runOne, runAllInFlight]);

  /* ─── history drawer (joined with metrics) ─────────── */
  const openHistory = useCallback(async (h) => {
    setHistoryFor(h);
    setHistoryLoading(true);
    setHistoryData(null);
    try {
      const [hist, res] = await Promise.all([
        API_HYPO.history(h.hypothesis_id),
        API_HYPO.results(h.hypothesis_id),
      ]);
      // Join run + result by run_id
      const resIx = {};
      for (const r of (res?.results || [])) resIx[r.run_id] = r;
      const enriched = (hist?.runs || []).map(run => ({
        ...run,
        metrics: resIx[run.run_id] || null,
      }));
      // Sort newest first
      enriched.sort((a, b) => (b.finished_at || b.started_at || '').localeCompare(a.finished_at || a.started_at || ''));
      setHistoryData({ count: enriched.length, runs: enriched });
    } catch (e) {
      setHistoryData({ error: e.message });
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  /* ─── strategy details modal ────────────────────────── */
  const [detailsFor, setDetailsFor] = useState(null);
  const openDetails = useCallback((h) => setDetailsFor(h), []);

  /* ─── compare matrix modal ──────────────────────────── */
  const [compareFor, setCompareFor] = useState(null);
  const [compareMatrix, setCompareMatrix] = useState({});  // "SYM/tf" → metrics
  const [compareInFlight, setCompareInFlight] = useState(false);

  const openCompare = useCallback(async (h) => {
    setCompareFor(h);
    setCompareMatrix({});
    setCompareInFlight(true);
    // For each supported (symbol, tf) — fetch latest result; if none, run.
    const tfsLower = (h.applicable_timeframes || []).map(s => s.toLowerCase());
    const allowedTfs = (TIMEFRAMES.filter(t =>
      tfsLower.length === 0 || tfsLower.includes(t.toLowerCase())));
    const tasks = [];
    for (const sym of SYMBOLS) {
      for (const t of allowedTfs) {
        tasks.push((async () => {
          const key = `${sym}/${t}`;
          // Try cached first, else run
          let m = await fetchLatestForFilter(h.hypothesis_id, sym, t);
          if (!m) {
            m = await runOne(h, sym, t);
          }
          setCompareMatrix(prev => ({ ...prev, [key]: m }));
        })());
      }
    }
    await Promise.all(tasks);
    setCompareInFlight(false);
  }, [runOne]);
  const closeCompare = () => { setCompareFor(null); setCompareMatrix({}); };

  /* ─── sorting ──────────────────────────────────────── */
  const sortedRows = useMemo(() => {
    const rows = strategies.map(h => ({
      h, m: resultsMap[h.hypothesis_id] || null,
    }));
    rows.sort((a, b) => {
      const aV = (a.m?.[sortBy] ?? -Infinity);
      const bV = (b.m?.[sortBy] ?? -Infinity);
      if (aV === bV) return 0;
      const cmp = aV > bV ? 1 : -1;
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [strategies, resultsMap, sortBy, sortDir]);

  const setSort = (col) => {
    if (sortBy === col) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortBy(col); setSortDir('desc'); }
  };

  /* ─── top stats ────────────────────────────────────── */
  const topStats = useMemo(() => {
    const ms = Object.values(resultsMap).filter(Boolean);
    if (!ms.length) return null;
    const bestPF = ms.reduce((m, x) => (x.profit_factor > (m?.profit_factor ?? 0) ? x : m), null);
    const avgWR = ms.reduce((s, x) => s + (x.win_rate || 0), 0) / ms.length;
    const last = ms.reduce((m, x) => (x.computed_at > (m?.computed_at ?? '') ? x : m), null);
    return { count: ms.length, bestPF, avgWR, last };
  }, [resultsMap]);

  /* ─────────────────────────── RENDER ─────────────────────────── */
  if (loading) {
    return (
      <Container data-testid="strategy-lab">
        <StateBox><Spinner /><h4>Loading Strategy Lab…</h4></StateBox>
      </Container>
    );
  }

  return (
    <Container data-testid="strategy-lab">
      {/* TOP STATS */}
      <StatsBar>
        <StatTile>
          <div className="label"><Beaker /> Strategies</div>
          <div className="value">{strategies.length}</div>
          <div className="sub">{strategies.filter(s => s.status === 'ACTIVE').length} active</div>
        </StatTile>
        <StatTile className="green">
          <div className="label"><BarChart3 /> Best PF</div>
          <div className="value">{topStats?.bestPF ? num(topStats.bestPF.profit_factor) : '—'}</div>
          <div className="sub">{topStats?.bestPF ? topStats.bestPF.hypothesis_id.replace(/_/g, ' ') : 'No runs yet'}</div>
        </StatTile>
        <StatTile className="amber">
          <div className="label"><Activity /> Avg Win Rate</div>
          <div className="value">{topStats ? pct(topStats.avgWR) : '—'}</div>
          <div className="sub">across {topStats?.count || 0} runs</div>
        </StatTile>
        <StatTile>
          <div className="label"><History /> Last Run</div>
          <div className="value" style={{ fontSize: 14, fontWeight: 600 }}>{topStats?.last ? fmtDate(topStats.last.computed_at) : 'Never'}</div>
          <div className="sub">{topStats?.last ? `${topStats.last.symbol} · ${topStats.last.timeframe}` : '—'}</div>
        </StatTile>
      </StatsBar>

      {error && (
        <ErrorBanner data-testid="error-banner">
          <AlertTriangle /> {error}
        </ErrorBanner>
      )}

      {/* BACKTEST BENCH */}
      <BenchCard data-testid="bench-card">
        <SectionHeader>
          <h3><Beaker size={14} /> Backtest Bench <span className="count">PROVE EDGE</span></h3>
        </SectionHeader>
        <div className="row">
          <div className="field">
            <span className="label">Symbol</span>
            <Select value={symbol} onChange={(e) => setSymbol(e.target.value)} data-testid="symbol-select">
              {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
            </Select>
          </div>
          <div className="field">
            <span className="label">Timeframe</span>
            <Select value={tf} onChange={(e) => setTf(e.target.value)} data-testid="tf-select">
              {TIMEFRAMES.map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
            </Select>
          </div>
          <div style={{ flex: 1 }} />
          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <SecondaryBtn onClick={loadAll} disabled={loading} data-testid="refresh-btn">
              <RefreshCw /> Refresh
            </SecondaryBtn>
          </div>
          <div className="field" style={{ alignSelf: 'flex-end' }}>
            <PrimaryBtn
              onClick={runAll}
              disabled={runAllInFlight || strategies.length === 0}
              className={runAllInFlight ? 'spinning' : ''}
              data-testid="run-all-btn"
            >
              {runAllInFlight ? <Loader2 /> : <Play />}
              {runAllInFlight ? `Running… (${runningIds.size}/${strategies.length})` : `Run All (${strategies.length})`}
            </PrimaryBtn>
          </div>
        </div>
      </BenchCard>

      {/* LEADERBOARD */}
      <SectionHeader>
        <h3><BarChart3 size={14} /> Results Leaderboard <span className="count">{Object.keys(resultsMap).length} of {strategies.length}</span></h3>
      </SectionHeader>
      <TableCard>
        <Table>
          <thead>
            <tr>
              <th $sortable={false}>Strategy</th>
              <th onClick={() => setSort('win_rate')}><span className="ic">WR <ArrowUpDown /></span></th>
              <th onClick={() => setSort('profit_factor')}><span className="ic">PF <ArrowUpDown /></span></th>
              <th onClick={() => setSort('expectancy')}><span className="ic">Exp <ArrowUpDown /></span></th>
              <th onClick={() => setSort('max_drawdown')}><span className="ic">DD <ArrowUpDown /></span></th>
              <th onClick={() => setSort('sharpe_ratio')}><span className="ic">Sharpe <ArrowUpDown /></span></th>
              <th onClick={() => setSort('sample_size')}><span className="ic">N <ArrowUpDown /></span></th>
              <th $sortable={false}>Best Regime</th>
              <th $sortable={false}>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {sortedRows.map(({ h, m }) => {
              const dir = dirOf(h);
              const br = bestRegime(m?.regime_breakdown);
              return (
                <tr key={h.hypothesis_id}>
                  <td>
                    <div className="name">
                      <DirChip $dir={dir}>
                        {dir === 'LONG' ? <TrendingUp /> : dir === 'SHORT' ? <TrendingDown /> : <Minus />}
                        {dir}
                      </DirChip>
                      <div>
                        <div className="strat-name">{h.name}</div>
                        <div className="strat-meta">{h.category} · {(h.applicable_timeframes || []).join(' / ')}</div>
                      </div>
                    </div>
                  </td>
                  <td className={m?.win_rate >= 0.55 ? 'green' : m?.win_rate >= 0.5 ? 'amber' : m ? 'red' : 'dim'}>
                    {m ? pct(m.win_rate) : '—'}
                  </td>
                  <td className={m?.profit_factor >= 2 ? 'green' : m?.profit_factor >= 1 ? 'amber' : m ? 'red' : 'dim'}>
                    {m ? num(m.profit_factor) : '—'}
                  </td>
                  <td className={m?.expectancy >= 1 ? 'green' : m?.expectancy >= 0 ? 'amber' : m ? 'red' : 'dim'}>
                    {m ? num(m.expectancy) : '—'}
                  </td>
                  <td className={m?.max_drawdown <= 0.1 ? 'green' : m?.max_drawdown <= 0.2 ? 'amber' : m ? 'red' : 'dim'}>
                    {m ? pct(m.max_drawdown) : '—'}
                  </td>
                  <td className={m?.sharpe_ratio >= 1 ? 'green' : m?.sharpe_ratio >= 0 ? 'amber' : m ? 'red' : 'dim'}>
                    {m ? num(m.sharpe_ratio) : '—'}
                  </td>
                  <td className="dim">{m?.sample_size != null ? m.sample_size : '—'}</td>
                  <td className="dim">
                    {br ? <span><strong style={{ color: T.text }}>{br.name}</strong> {pct(br.wr)}</span> : '—'}
                  </td>
                  <td>
                    {m?.verdict ? <VerdictPill $verdict={m.verdict}>{verdictIcon(m.verdict)} {m.verdict}</VerdictPill> : <VerdictPill>—</VerdictPill>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </TableCard>

      {/* STRATEGY CARDS */}
      <SectionHeader>
        <h3><Beaker size={14} /> Strategy Registry <span className="count">{strategies.length}</span></h3>
      </SectionHeader>
      <Grid data-testid="strategy-grid">
        {strategies.map(h => {
          const m = resultsMap[h.hypothesis_id];
          const dir = dirOf(h);
          const isRunning = runningIds.has(h.hypothesis_id);
          const tfs = tfsOf(h);
          const tfsLower = tfs.map(s => s.toLowerCase());
          const tfSupported = tfsLower.length === 0 || tfsLower.includes(tf.toLowerCase());

          return (
            <Card key={h.hypothesis_id} data-testid={`card-${h.hypothesis_id}`}>
              <CardHead>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <h4 className="name">{h.name}</h4>
                  <div className="desc">{h.description}</div>
                </div>
                <CategoryChip>{h.category}</CategoryChip>
              </CardHead>

              <CardChips>
                <DirChip $dir={dir}>
                  {dir === 'LONG' ? <TrendingUp /> : dir === 'SHORT' ? <TrendingDown /> : <Minus />}
                  {dir}
                </DirChip>
                {tfs.map(t => (
                  <SmallChip key={t} style={{
                    borderColor: t.toLowerCase() === tf.toLowerCase() ? T.primary : T.border,
                    color: t.toLowerCase() === tf.toLowerCase() ? T.primary : T.text2,
                  }}>{t.toUpperCase()}</SmallChip>
                ))}
                {h.expected_outcome?.target_move_pct != null && (
                  <SmallChip>Target {h.expected_outcome.target_move_pct}%</SmallChip>
                )}
                {h.expected_outcome?.time_horizon_candles != null && (
                  <SmallChip>{h.expected_outcome.time_horizon_candles} candles</SmallChip>
                )}
              </CardChips>

              <Conditions>
                <div className="head">Condition Set ({(h.condition_set || []).length} rules)</div>
                {(h.condition_set || []).map((c, i) => (
                  <Cond key={i}>
                    <span className="indicator">{c.indicator.replace(/_/g, ' ')}</span>
                    <span className="op">{c.operator}</span>
                    <span className="val">{String(c.value)}</span>
                    <span className="weight">w {c.weight}</span>
                  </Cond>
                ))}
              </Conditions>

              <KPIs>
                <KPI className={m?.win_rate >= 0.55 ? 'green' : m?.win_rate >= 0.5 ? 'amber' : m ? 'red' : 'dim'}>
                  <div className="l">WR</div>
                  <div className="v">{m ? pct(m.win_rate) : '—'}</div>
                </KPI>
                <KPI className={m?.profit_factor >= 2 ? 'green' : m?.profit_factor >= 1 ? 'amber' : m ? 'red' : 'dim'}>
                  <div className="l">PF</div>
                  <div className="v">{m ? num(m.profit_factor) : '—'}</div>
                </KPI>
                <KPI className={m?.expectancy >= 1 ? 'green' : m?.expectancy >= 0 ? 'amber' : m ? 'red' : 'dim'}>
                  <div className="l">Exp</div>
                  <div className="v">{m ? num(m.expectancy) : '—'}</div>
                </KPI>
                <KPI className={m?.max_drawdown <= 0.1 ? 'green' : m?.max_drawdown <= 0.2 ? 'amber' : m ? 'red' : 'dim'}>
                  <div className="l">DD</div>
                  <div className="v">{m ? pct(m.max_drawdown) : '—'}</div>
                </KPI>
              </KPIs>

              {!tfSupported && (
                <div style={{ fontSize: 11, color: T.amber, fontWeight: 600 }}>
                  <AlertTriangle size={11} style={{ verticalAlign: '-2px', marginRight: 4 }} />
                  Strategy not designed for {tf.toUpperCase()} — supported: {tfs.join(', ')}
                </div>
              )}

              <Actions>
                <PrimaryBtn
                  onClick={() => runOne(h)}
                  disabled={isRunning || !tfSupported}
                  className={isRunning ? 'spinning' : ''}
                  data-testid={`run-${h.hypothesis_id}`}
                  style={{ flex: 1 }}
                >
                  {isRunning ? <Loader2 /> : <Play />}
                  {isRunning ? 'Running…' : (m ? 'Re-run' : 'Run Backtest')}
                </PrimaryBtn>
                <GhostBtn onClick={() => openDetails(h)} data-testid={`details-${h.hypothesis_id}`}>
                  <Beaker /> Details
                </GhostBtn>
                <GhostBtn onClick={() => openCompare(h)} data-testid={`compare-${h.hypothesis_id}`}>
                  <ArrowUpDown /> Compare
                </GhostBtn>
                <GhostBtn onClick={() => openHistory(h)} data-testid={`history-${h.hypothesis_id}`}>
                  <History /> History
                </GhostBtn>
              </Actions>
            </Card>
          );
        })}
      </Grid>

      {/* HISTORY DRAWER */}
      <Backdrop $open={!!historyFor} onClick={() => setHistoryFor(null)} />
      <Drawer $open={!!historyFor} data-testid="history-drawer">
        {historyFor && (
          <>
            <DrawerHead>
              <div>
                <h4>Run History</h4>
                <div className="sub">{historyFor.name}</div>
              </div>
              <button className="close" onClick={() => setHistoryFor(null)} aria-label="Close">
                <X />
              </button>
            </DrawerHead>
            <DrawerBody>
              {historyLoading && <StateBox><Spinner /><h4>Loading…</h4></StateBox>}
              {!historyLoading && historyData?.error && (
                <ErrorBanner><AlertTriangle /> {historyData.error}</ErrorBanner>
              )}
              {!historyLoading && historyData && !historyData.error && (
                <>
                  <div style={{ fontSize: 12, color: T.text3, marginBottom: 14, fontWeight: 600 }}>
                    {historyData.count || 0} run{(historyData.count || 0) === 1 ? '' : 's'} recorded
                  </div>
                  {(historyData.runs || []).length === 0 ? (
                    <StateBox><History /><h4>No runs yet</h4><p>Run a backtest to populate history.</p></StateBox>
                  ) : (
                    (historyData.runs || []).map(r => {
                      const mt = r.metrics;
                      return (
                        <RunRow key={r.run_id} style={{ display: 'block' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, marginBottom: 8 }}>
                            <div>
                              <div className="id">{r.run_id?.slice(0, 14) || '—'}</div>
                              <div className="meta" style={{ fontSize: 10, marginTop: 2 }}>
                                {fmtDate(r.started_at)}
                              </div>
                              <div className="meta" style={{ marginTop: 4 }}>
                                <span className="k">{r.symbol || '—'}</span> · <span className="k">{(r.timeframe || '').toUpperCase()}</span>
                                {r.sample_size != null && <> · n=<span className="k">{r.sample_size}</span></>}
                                {r.triggers_found != null && <> · triggers=<span className="k">{r.triggers_found}</span></>}
                              </div>
                            </div>
                            <span className={`status ${r.status || 'PENDING'}`}>{r.status || 'PENDING'}</span>
                          </div>
                          {mt && (
                            <div style={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(4, 1fr)',
                              gap: 6,
                              marginTop: 6,
                              fontSize: 11,
                            }}>
                              <div style={{ background: T.surface, border: `1px solid ${T.border}`, padding: '6px 8px', borderRadius: 6 }}>
                                <div style={{ color: T.text3, fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>WR</div>
                                <div style={{ fontWeight: 700, color: mt.win_rate >= 0.55 ? T.green : mt.win_rate >= 0.5 ? T.amber : T.red }}>{pct(mt.win_rate)}</div>
                              </div>
                              <div style={{ background: T.surface, border: `1px solid ${T.border}`, padding: '6px 8px', borderRadius: 6 }}>
                                <div style={{ color: T.text3, fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>PF</div>
                                <div style={{ fontWeight: 700, color: mt.profit_factor >= 2 ? T.green : mt.profit_factor >= 1 ? T.amber : T.red }}>{num(mt.profit_factor)}</div>
                              </div>
                              <div style={{ background: T.surface, border: `1px solid ${T.border}`, padding: '6px 8px', borderRadius: 6 }}>
                                <div style={{ color: T.text3, fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>Exp</div>
                                <div style={{ fontWeight: 700, color: mt.expectancy >= 1 ? T.green : mt.expectancy >= 0 ? T.amber : T.red }}>{num(mt.expectancy)}</div>
                              </div>
                              <div style={{ background: T.surface, border: `1px solid ${T.border}`, padding: '6px 8px', borderRadius: 6 }}>
                                <div style={{ color: T.text3, fontSize: 9, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>DD</div>
                                <div style={{ fontWeight: 700, color: mt.max_drawdown <= 0.1 ? T.green : mt.max_drawdown <= 0.2 ? T.amber : T.red }}>{pct(mt.max_drawdown)}</div>
                              </div>
                            </div>
                          )}
                          {r.error && <div style={{ color: T.red, marginTop: 6, fontSize: 11 }}>Error: {r.error}</div>}
                        </RunRow>
                      );
                    })
                  )}
                </>
              )}
            </DrawerBody>
          </>
        )}
      </Drawer>
      {/* STRATEGY DETAILS MODAL */}
      <Backdrop $open={!!detailsFor} onClick={() => setDetailsFor(null)} />
      <Drawer $open={!!detailsFor} data-testid="details-drawer">
        {detailsFor && (() => {
          const h = detailsFor;
          const eo = h.expected_outcome || {};
          return (
            <>
              <DrawerHead>
                <div>
                  <h4>{h.name}</h4>
                  <div className="sub">{h.hypothesis_id} · v{h.version} · {h.status}</div>
                </div>
                <button className="close" onClick={() => setDetailsFor(null)} aria-label="Close"><X /></button>
              </DrawerHead>
              <DrawerBody>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
                  <CategoryChip>{h.category}</CategoryChip>
                  <DirChip $dir={dirOf(h)}>{dirOf(h) === 'LONG' ? <TrendingUp /> : dirOf(h) === 'SHORT' ? <TrendingDown /> : <Minus />}{dirOf(h)}</DirChip>
                  {(h.applicable_timeframes || []).map(t => <SmallChip key={t}>{t.toUpperCase()}</SmallChip>)}
                </div>
                {h.description && (
                  <div style={{ background: T.surface2, padding: '12px 14px', borderRadius: 10, fontSize: 13, color: T.text2, lineHeight: 1.55, marginBottom: 14, borderLeft: `3px solid ${T.primary}` }}>
                    {h.description}
                  </div>
                )}
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', color: T.text3, textTransform: 'uppercase', marginBottom: 8 }}>Expected Outcome</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                    <KPI><div className="l">Direction</div><div className="v">{eo.direction || '—'}</div></KPI>
                    <KPI><div className="l">Target Move</div><div className="v">{eo.target_move_pct != null ? `${eo.target_move_pct}%` : '—'}</div></KPI>
                    <KPI><div className="l">Time Horizon</div><div className="v">{eo.time_horizon_candles != null ? `${eo.time_horizon_candles} candles` : '—'}</div></KPI>
                    <KPI><div className="l">Stop Loss</div><div className="v">{eo.stop_loss_pct != null ? `${eo.stop_loss_pct}%` : '—'}</div></KPI>
                  </div>
                </div>
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', color: T.text3, textTransform: 'uppercase', marginBottom: 8 }}>
                    Condition Set ({(h.condition_set || []).length} rules)
                  </div>
                  {(h.condition_set || []).map((c, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'baseline', gap: 8,
                      padding: '10px 12px', background: T.surface2,
                      border: `1px solid ${T.border}`, borderRadius: 8,
                      marginBottom: 6, fontSize: 12,
                    }}>
                      <span style={{ fontWeight: 700, color: T.text }}>{c.indicator.replace(/_/g, ' ')}</span>
                      <span style={{ color: T.text3, fontFamily: 'SF Mono, ui-monospace, monospace', fontWeight: 600 }}>{c.operator}</span>
                      <span style={{ color: T.primary, fontWeight: 700, fontFamily: 'SF Mono, ui-monospace, monospace' }}>{String(c.value)}</span>
                      <span style={{ marginLeft: 'auto', fontSize: 10, color: T.text3, background: T.surface, border: `1px solid ${T.border}`, padding: '1px 6px', borderRadius: 4, fontWeight: 600 }}>weight {c.weight}</span>
                    </div>
                  ))}
                </div>
                {(h.applicable_regimes && h.applicable_regimes.length > 0) && (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', color: T.text3, textTransform: 'uppercase', marginBottom: 6 }}>Applicable Regimes</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {h.applicable_regimes.map(r => <SmallChip key={r}>{r}</SmallChip>)}
                    </div>
                  </div>
                )}
                {h.tags && h.tags.length > 0 && (
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.07em', color: T.text3, textTransform: 'uppercase', marginBottom: 6 }}>Tags</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {h.tags.map(t => <SmallChip key={t}>{t}</SmallChip>)}
                    </div>
                  </div>
                )}
              </DrawerBody>
            </>
          );
        })()}
      </Drawer>

      {/* COMPARE MATRIX MODAL */}
      <Backdrop $open={!!compareFor} onClick={closeCompare} />
      <Drawer $open={!!compareFor} data-testid="compare-drawer" style={{ width: 640 }}>
        {compareFor && (
          <>
            <DrawerHead>
              <div>
                <h4>Compare: {compareFor.name}</h4>
                <div className="sub">Symbol × Timeframe matrix · {compareInFlight ? 'running…' : 'ready'}</div>
              </div>
              <button className="close" onClick={closeCompare} aria-label="Close"><X /></button>
            </DrawerHead>
            <DrawerBody>
              <Table>
                <thead>
                  <tr>
                    <th $sortable={false}>Symbol \ TF</th>
                    {TIMEFRAMES.map(t => <th key={t} $sortable={false}>{t.toUpperCase()}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {SYMBOLS.map(sym => (
                    <tr key={sym}>
                      <td><strong>{sym.replace('USDT','')}</strong></td>
                      {TIMEFRAMES.map(t => {
                        const key = `${sym}/${t}`;
                        const m = compareMatrix[key];
                        const tfsLower = (compareFor.applicable_timeframes || []).map(s => s.toLowerCase());
                        const supported = tfsLower.length === 0 || tfsLower.includes(t.toLowerCase());
                        if (!supported) {
                          return <td key={t} className="dim" style={{ fontSize: 11 }}>n/a</td>;
                        }
                        if (!m) {
                          return <td key={t} className="dim"><Spinner style={{ width: 14, height: 14 }} /></td>;
                        }
                        return (
                          <td key={t} style={{ padding: '10px 12px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                              <div style={{ fontSize: 13, fontWeight: 700, color: m.profit_factor >= 2 ? T.green : m.profit_factor >= 1 ? T.amber : T.red }}>
                                PF {num(m.profit_factor)}
                              </div>
                              <div style={{ fontSize: 11, color: T.text2, fontWeight: 600 }}>
                                WR {pct(m.win_rate)} · DD {pct(m.max_drawdown)}
                              </div>
                              <div style={{ fontSize: 10, color: T.text3 }}>n={m.sample_size}</div>
                              {m.verdict && (
                                <VerdictPill $verdict={m.verdict} style={{ alignSelf: 'flex-start', marginTop: 3 }}>
                                  {verdictIcon(m.verdict)} {m.verdict}
                                </VerdictPill>
                              )}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </Table>
              <div style={{ marginTop: 14, fontSize: 11, color: T.text3, lineHeight: 1.6 }}>
                {compareInFlight
                  ? 'Cells fill in as backtests complete. Existing results are reused without re-running.'
                  : 'All cells loaded. Best PF cell wins this strategy\'s deployment slot.'}
              </div>
            </DrawerBody>
          </>
        )}
      </Drawer>
    </Container>
  );
};

export default HypothesesView;
