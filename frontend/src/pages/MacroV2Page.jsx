/**
 * Macro V2 — Capital Flow Intelligence Layer
 * 
 * Regime probability model. CPI. Risk-Off. Capital Flow Map.
 * Drivers decomposition. Impact on Core Engine.
 * Style: Core Engine sibling.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, Loader2, AlertTriangle, Shield, TrendingUp, TrendingDown, Minus, ArrowRight, Check, Ban } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const REGIME_COLORS = {
  FLIGHT_TO_BTC: '#6366f1',
  ALT_ROTATION: '#16a34a',
  CAPITAL_EXIT: '#dc2626',
  NEUTRAL: '#94a3b8',
};

const REGIME_LABELS = {
  FLIGHT_TO_BTC: 'Flight to BTC',
  ALT_ROTATION: 'Alt Rotation',
  CAPITAL_EXIT: 'Capital Exit',
  NEUTRAL: 'Neutral',
};

const REGIME_TIPS = {
  FLIGHT_TO_BTC: 'Capital moves to BTC as safe haven. Alts underperform. Defensive positioning recommended — avoid aggressive alt exposure',
  ALT_ROTATION: 'Capital rotating into alts. Risk-on environment. Good conditions for alt entries, but watch for reversal signals',
  CAPITAL_EXIT: 'Capital leaving crypto into stables/cash. Strong risk-off. Reduce exposure, no new positions recommended',
  NEUTRAL: 'Mixed signals, no clear capital direction. Markets indecisive. Low-conviction environment — smaller position sizes',
};

const PRESSURE_COLORS = {
  IN: '#16a34a', OUT: '#dc2626', FLAT: '#94a3b8',
  OUTPERFORMING: '#16a34a', UNDERPERFORMING: '#dc2626', INLINE: '#94a3b8',
  RISK_SHELTER: '#d97706', DEPLOYING: '#16a34a',
};

function Tip({ text, children, block }) {
  const [show, setShow] = useState(false);
  if (!text) return children;
  const Tag = block ? 'div' : 'span';
  return (
    <Tag className={`relative ${block ? 'block' : 'inline-flex'}`} onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute z-50 left-0 top-full mt-1.5 w-72 px-3 py-2 rounded-lg pointer-events-none text-[12px]"
          style={{ background: '#0f172a', color: '#e2e8f0', boxShadow: '0 8px 24px rgba(0,0,0,0.25)' }}>
          {text}
        </span>
      )}
    </Tag>
  );
}

function SL({ children }) {
  return <div className="text-[11px] uppercase tracking-wider font-semibold mb-3" style={{ color: '#94a3b8' }}>{children}</div>;
}

/* ═══════════ MACRO OVERVIEW (Hero) ═══════════ */
function MacroOverview({ data }) {
  const c = data.computed;
  const regime = c.regime;
  const rc = REGIME_COLORS[regime] || '#94a3b8';
  const probs = c.regimeProbs || {};
  const sorted = Object.entries(probs).sort((a, b) => b[1] - a[1]);
  const second = sorted[1];

  const riskPct = Math.round(c.riskOffProb * 100);
  const riskColor = riskPct > 70 ? '#dc2626' : riskPct > 40 ? '#d97706' : '#16a34a';

  return (
    <div data-testid="macro-overview" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Macro Regime</SL>
      <Tip text={REGIME_TIPS[regime] || ''}>
        <div className="flex items-baseline gap-3 mb-1">
          <span className="text-[28px] font-bold" style={{ color: rc }}>{REGIME_LABELS[regime] || regime}</span>
          <span className="text-[15px] font-semibold" style={{ color: rc }}>{Math.round(sorted[0]?.[1] * 100)}%</span>
        </div>
      </Tip>
      {second && (
        <div className="text-[12px] mb-4" style={{ color: '#64748b' }}>
          Next: {REGIME_LABELS[second[0]] || second[0]} {Math.round(second[1] * 100)}%
        </div>
      )}

      <div className="flex gap-5 flex-wrap">
        <KpiChip label="Risk-Off" value={`${riskPct}%`} color={riskColor}
          tip="Probability that capital is rotating into defensive assets (BTC/stables)" />
        <KpiChip label="CPI" value={c.cpi > 0 ? `+${c.cpi.toFixed(2)}` : c.cpi.toFixed(2)}
          color={c.cpi > 0.5 ? '#6366f1' : c.cpi < -0.5 ? '#16a34a' : '#64748b'}
          tip="Capital Pressure Index — measures 7d dominance shifts and relative strength" />
        <KpiChip label="Confidence" value={`${c.macroMult.toFixed(2)}x`}
          color={c.macroMult > 0.8 ? '#16a34a' : c.macroMult > 0.6 ? '#d97706' : '#dc2626'}
          tip="Macro scales signal confidence but does not change direction" />
        {c.strongActionsBlocked && (
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" style={{ color: '#ef4444' }} />
            <span className="text-[11px] font-bold tracking-wide" style={{ color: '#ef4444' }}>BLOCKED</span>
          </div>
        )}
      </div>

      {c.notes && c.notes.length > 0 && (
        <div className="mt-3 space-y-1">
          {c.notes.map((n, i) => (
            <div key={i} className="text-[11px] font-medium" style={{ color: '#d97706' }}>{n}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function KpiChip({ label, value, color, tip }) {
  return (
    <Tip text={tip}>
      <div>
        <div className="text-[11px] uppercase font-semibold" style={{ color: '#94a3b8' }}>{label}</div>
        <div className="text-[22px] font-bold tabular-nums" style={{ color }}>{value}</div>
      </div>
    </Tip>
  );
}

/* ═══════════ RAW MARKET CONTEXT ═══════════ */
function MarketContext({ data }) {
  const r = data.raw;
  const fg = r.fearGreed;
  const fgColor = fg <= 25 ? '#dc2626' : fg >= 75 ? '#16a34a' : fg >= 45 ? '#d97706' : '#f97316';
  const fgLabel = fg <= 20 ? 'Extreme Fear' : fg <= 40 ? 'Fear' : fg <= 60 ? 'Neutral' : fg <= 80 ? 'Greed' : 'Extreme Greed';
  const fgTip = fg <= 20 ? 'Panic in the market. Historically — contrarian buy zone, but high risk of further drops'
    : fg <= 40 ? 'Market fearful. Caution warranted. Entry opportunities exist but with tight risk'
    : fg <= 60 ? 'Market calm, no emotional extremes. Standard trading conditions'
    : fg <= 80 ? 'Growing optimism. Trend is likely up, but watch for overextension'
    : 'Euphoria detected. Historically — distribution zone. High probability of correction';

  return (
    <div data-testid="macro-market-context" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Market Context</SL>
      <Tip text={fgTip}>
        <div className="flex items-baseline gap-3 mb-3">
          <span className="text-[28px] font-bold tabular-nums" style={{ color: fgColor }}>{Math.round(fg)}</span>
          <span className="text-[13px] font-semibold" style={{ color: fgColor }}>{fgLabel}</span>
        </div>
      </Tip>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        <CtxRow label="BTC Price" value={`$${(r.btcPrice || 0).toLocaleString('en', { maximumFractionDigits: 0 })}`}
          tip="Current BTC market price" />
        <CtxRow label="BTC Dom" value={`${r.btcDom}%`}
          tip={r.btcDom > 55 ? `${r.btcDom}% — BTC dominant. Capital concentrated in BTC, alts starved of liquidity` : r.btcDom < 45 ? `${r.btcDom}% — BTC weak. Alt season territory, capital dispersing` : `${r.btcDom}% — Balanced. No strong capital concentration`} />
        <CtxRow label="Stable Dom" value={`${r.stableDom}%`}
          tip={r.stableDom > 12 ? `${r.stableDom}% — High. Capital sitting in stables = risk-off sentiment` : r.stableDom < 8 ? `${r.stableDom}% — Low. Capital deployed = risk-on` : `${r.stableDom}% — Normal range`} />
        <CtxRow label="Alt Dom" value={`${r.altDom}%`}
          tip={r.altDom > 40 ? `${r.altDom}% — Alts gaining share. Healthy alt rotation` : r.altDom < 30 ? `${r.altDom}% — Alts compressed. Capital fled to BTC/stables` : `${r.altDom}% — Standard alt market share`} />
        <CtxRow label="Vol (7d)" value={r.marketVol ? `${(r.marketVol * 100).toFixed(1)}%` : '-'}
          tip={r.marketVol > 0.04 ? 'High volatility — larger price swings, wider risk' : r.marketVol > 0.02 ? 'Normal volatility' : 'Low volatility — calm market, potential for breakout'} />
        <CtxRow label="Data" value={data.dataSource === 'live' ? 'Live' : 'Synthetic'} color={data.dataSource === 'live' ? '#16a34a' : '#d97706'}
          tip={data.dataSource === 'live' ? 'Real market data — CryptoCompare + CoinPaprika + Alternative.me' : 'Simulated data — live API sources unavailable'} />
      </div>
    </div>
  );
}

function CtxRow({ label, value, color, tip }) {
  const inner = (
    <div className="flex justify-between items-center">
      <span className="text-[12px]" style={{ color: '#64748b' }}>{label}</span>
      <span className="text-[13px] font-semibold tabular-nums" style={{ color: color || '#0f172a' }}>{value}</span>
    </div>
  );
  return tip ? <Tip text={tip} block>{inner}</Tip> : inner;
}

/* ═══════════ CAPITAL FLOW MAP ═══════════ */
function CapitalFlowMap({ data }) {
  const cf = data.capitalFlow;
  if (!cf || !cf.btc) return null;

  const flowTips = {
    btc: cf.btc.dominance > 55
      ? `BTC ${cf.btc.dominance}% — High dominance. Capital concentrated in BTC, alts starved of liquidity. Defensive market`
      : cf.btc.dominance < 45
      ? `BTC ${cf.btc.dominance}% — Low dominance. Capital dispersing to alts = risk-on environment`
      : `BTC ${cf.btc.dominance}% — Balanced BTC allocation, no extreme concentration`,
    alt: cf.alt.pressure === 'OUTPERFORMING'
      ? `ALT ${cf.alt.dominance}% — Alts outperforming BTC. Risk-on, alt rotation active. Good for alt entries`
      : cf.alt.pressure === 'UNDERPERFORMING'
      ? `ALT ${cf.alt.dominance}% — Alts underperforming. Capital leaving alts for BTC/stables. Reduce alt exposure`
      : `ALT ${cf.alt.dominance}% — Alts tracking BTC. No clear alpha, neutral conditions`,
    stable: cf.stable.dominance > 12
      ? `STABLE ${cf.stable.dominance}% — High stable share. Capital in shelter = fear/caution. Market risk-off`
      : cf.stable.pressure === 'DEPLOYING'
      ? `STABLE ${cf.stable.dominance}% — Stables deploying into market. Risk appetite increasing`
      : `STABLE ${cf.stable.dominance}% — Normal stable allocation, no extreme positioning`,
  };

  const flows = [
    { key: 'btc', label: 'BTC', color: '#6366f1', ...cf.btc },
    { key: 'alt', label: 'ALT', color: '#16a34a', ...cf.alt },
    { key: 'stable', label: 'STABLE', color: '#d97706', ...cf.stable },
  ];

  return (
    <div data-testid="macro-capital-flow" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Capital Flow Map</SL>
      <div className="grid grid-cols-3 gap-4">
        {flows.map(f => (
          <Tip key={f.key} text={flowTips[f.key]} block>
            <div className="rounded-xl p-4" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[14px] font-bold" style={{ color: f.color }}>{f.label}</span>
                <span className="text-[11px] font-bold"
                  style={{ color: PRESSURE_COLORS[f.pressure] || '#94a3b8' }}>
                  {f.pressure}
                </span>
              </div>
              <div className="text-[26px] font-bold tabular-nums mb-1" style={{ color: '#0f172a' }}>
                {f.dominance}%
              </div>
              <div className="flex gap-4">
                <DeltaChip label="7d" value={f.delta7d} />
                <DeltaChip label="30d" value={f.delta30d} />
              </div>
            </div>
          </Tip>
        ))}
      </div>
    </div>
  );
}

function DeltaChip({ label, value }) {
  const color = value > 0.1 ? '#16a34a' : value < -0.1 ? '#dc2626' : '#94a3b8';
  const icon = value > 0.1 ? <TrendingUp className="w-3 h-3" /> : value < -0.1 ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />;
  return (
    <div className="flex items-center gap-1">
      <span className="text-[11px]" style={{ color: '#94a3b8' }}>{label}</span>
      <span className="flex items-center gap-0.5 text-[12px] font-semibold tabular-nums" style={{ color }}>
        {icon} {value > 0 ? '+' : ''}{value.toFixed(2)}
      </span>
    </div>
  );
}

/* ═══════════ REGIME PROBABILITY GRID ═══════════ */
function RegimeGrid({ data }) {
  const c = data.computed;
  const probs = c.regimeProbs || {};
  const sorted = Object.entries(probs).sort((a, b) => b[1] - a[1]);
  const regime = c.regime;

  return (
    <div data-testid="macro-regime-grid" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Regime Probabilities</SL>
      <div className="space-y-2">
        {sorted.map(([key, prob]) => {
          const isCurrent = key === regime;
          const color = REGIME_COLORS[key] || '#94a3b8';
          const pct = Math.round(prob * 100);
          return (
            <div key={key} data-testid={`macro-regime-${key}`}
              className="flex items-center gap-3 rounded-xl px-4 py-3 transition-all"
              style={{
                background: isCurrent ? `${color}08` : '#f8fafc',
                border: `1.5px solid ${isCurrent ? color : '#e2e8f0'}`,
              }}>
              <div className="flex-1 min-w-0">
                <Tip text={REGIME_TIPS[key] || ''}>
                  <div className="text-[13px] font-bold" style={{ color: isCurrent ? color : '#334155' }}>
                    {REGIME_LABELS[key] || key}
                  </div>
                </Tip>
              </div>
              <div className="text-[18px] font-bold tabular-nums" style={{ color }}>{pct}%</div>
              <div className="w-24 h-2 rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════ IMPACT ON DECISIONS ═══════════ */
function ImpactPanel({ data }) {
  const impact = data.impact;
  const c = data.computed;
  if (!impact) return null;

  return (
    <div data-testid="macro-impact" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Impact on Core Engine</SL>
        <div className="space-y-3">
          <ImpactRow label="Confidence scaled to" value={`${impact.aggressionScale.toFixed(2)}x`}
            color={impact.aggressionScale > 0.8 ? '#16a34a' : impact.aggressionScale > 0.6 ? '#d97706' : '#dc2626'}
            tip={impact.aggressionScale > 0.8 ? 'Confidence high. Macro conditions supportive for normal positioning' : impact.aggressionScale > 0.6 ? 'Confidence reduced. Macro caution — reduce position sizes by ~30-40%' : 'Confidence low. Macro risk elevated — minimize exposure, defensive only'} />
          {impact.riskSurfaceImpact > 0 && (
            <ImpactRow label="Risk surface increase" value={`+${impact.riskSurfaceImpact}%`} color="#dc2626"
              tip={`Macro conditions inflate perceived risk by ${impact.riskSurfaceImpact}%. Higher risk = tighter stops and smaller sizes`} />
          )}
          <ImpactRow label="Strong actions" value={impact.strongActionsBlocked ? 'BLOCKED' : 'ALLOWED'}
            color={impact.strongActionsBlocked ? '#dc2626' : '#16a34a'}
            icon={impact.strongActionsBlocked ? <Ban className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            tip={impact.strongActionsBlocked ? 'Aggressive entries/exits are blocked by macro. Only defensive actions available' : 'Macro allows all action types including aggressive entries'} />
          <ImpactRow label="Alt exposure" value={impact.altExposureReduced ? 'REDUCED' : 'NORMAL'}
            color={impact.altExposureReduced ? '#d97706' : '#16a34a'}
            icon={impact.altExposureReduced ? <Shield className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
            tip={impact.altExposureReduced ? 'Capital concentrating in BTC/stables — reduce alt positions, favor BTC' : 'Healthy alt market conditions — normal alt allocation'} />
        </div>
    </div>
  );
}

function ImpactRow({ label, value, color, icon, tip }) {
  const inner = (
    <div className="flex items-center justify-between py-1.5 border-b" style={{ borderColor: '#f1f5f9' }}>
      <span className="text-[12px] font-medium" style={{ color: '#64748b' }}>{label}</span>
      <span className="flex items-center gap-1.5 text-[13px] font-bold" style={{ color }}>
        {icon}{value}
      </span>
    </div>
  );
  return tip ? <Tip text={tip} block>{inner}</Tip> : inner;
}

/* ═══════════ DRIVERS DECOMPOSITION ═══════════ */
function DriversPanel({ data }) {
  const drivers = data.drivers;
  const riskoff = data.riskoffDrivers;
  if (!drivers) return null;

  const cpiItems = [
    { key: 'btc_dom_delta', label: 'BTC Dominance Shift' },
    { key: 'stable_dom_delta', label: 'Stable Dominance Shift' },
    { key: 'btc_momentum', label: 'BTC Momentum' },
    { key: 'alt_relative_strength', label: 'Alt Relative Strength' },
    { key: 'fear_greed_impact', label: 'Fear & Greed' },
  ];

  const riskItems = [
    { key: 'stable_dom', label: 'Stable Dom' },
    { key: 'fear_greed', label: 'Fear & Greed' },
    { key: 'volatility', label: 'Volatility' },
    { key: 'btc_drawdown', label: 'BTC Drawdown' },
  ];

  return (
    <div data-testid="macro-drivers" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>CPI Drivers</SL>
      <div className="space-y-1.5 mb-5">
        {cpiItems.map(({ key, label }) => (
          <DriverBar key={key} label={label} value={drivers[key] || 0} />
        ))}
      </div>

      <SL>Risk-Off Drivers</SL>
      <div className="space-y-1.5">
        {riskItems.map(({ key, label }) => (
          <DriverBar key={key} label={label} value={riskoff?.[key] || 0} />
        ))}
      </div>
    </div>
  );
}

function DriverBar({ label, value }) {
  const absVal = Math.abs(value);
  const maxWidth = 100;
  const width = Math.min(absVal * 50, maxWidth);
  const color = value > 0.05 ? '#6366f1' : value < -0.05 ? '#dc2626' : '#94a3b8';

  return (
    <div className="flex items-center gap-3">
      <span className="text-[11px] w-36 shrink-0 text-right" style={{ color: '#64748b' }}>{label}</span>
      <div className="flex-1 flex items-center h-5">
        <div className="relative w-full h-2 rounded-full" style={{ background: '#f1f5f9' }}>
          {value >= 0 ? (
            <div className="absolute left-1/2 h-full rounded-r-full transition-all" style={{ width: `${width / 2}%`, background: color }} />
          ) : (
            <div className="absolute right-1/2 h-full rounded-l-full transition-all" style={{ width: `${width / 2}%`, background: color }} />
          )}
          <div className="absolute left-1/2 top-0 bottom-0 w-px" style={{ background: '#cbd5e1' }} />
        </div>
      </div>
      <span className="text-[11px] font-semibold tabular-nums w-14 text-right" style={{ color }}>
        {value > 0 ? '+' : ''}{value.toFixed(2)}
      </span>
    </div>
  );
}

/* ═══════════ HISTORY CHART (Interactive) ═══════════ */
function HistoryPanel({ historyData, historyRange, setHistoryRange }) {
  const points = historyData?.points || [];
  const [hoverIdx, setHoverIdx] = useState(null);
  const svgRef = useRef(null);

  const sliced = points.slice(-historyRange);
  const w = 600, h = 140, pad = 4;
  const step = (w - pad * 2) / Math.max(sliced.length - 1, 1);

  const handleMouseMove = useCallback((e) => {
    if (!svgRef.current || !sliced.length) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const svgX = (mx / rect.width) * w;
    const idx = Math.round((svgX - pad) / step);
    setHoverIdx(Math.max(0, Math.min(sliced.length - 1, idx)));
  }, [sliced.length, step]);

  const handleMouseLeave = useCallback(() => setHoverIdx(null), []);

  if (!points.length) return null;

  const ranges = [
    { value: 30, label: '30d' },
    { value: 60, label: '60d' },
    { value: 90, label: '90d' },
  ];

  const getXY = (idx, key, min, max) => {
    const x = pad + idx * step;
    const norm = ((sliced[idx]?.[key] || 0) - min) / (max - min || 1);
    const y = h - pad - norm * (h - pad * 2);
    return { x, y };
  };

  const buildPath = (key, min, max) => {
    return sliced.map((_, i) => {
      const { x, y } = getXY(i, key, min, max);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  };

  const fgPath = buildPath('fearGreed', 0, 100);
  const roPath = buildPath('riskOffProb', 0, 1);

  // Regime color segments
  const regimeSegments = [];
  let segStart = 0;
  let segRegime = sliced[0]?.regime;
  for (let i = 1; i <= sliced.length; i++) {
    if (i === sliced.length || sliced[i]?.regime !== segRegime) {
      regimeSegments.push({
        x: pad + segStart * step,
        width: (i - segStart) * step,
        color: REGIME_COLORS[segRegime] || '#94a3b8',
      });
      if (i < sliced.length) {
        segStart = i;
        segRegime = sliced[i].regime;
      }
    }
  }

  // Hover point data
  const hp = hoverIdx !== null ? sliced[hoverIdx] : null;
  const hoverX = hoverIdx !== null ? pad + hoverIdx * step : 0;
  const hoverDate = hp ? new Date(hp.t * 1000).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '';

  return (
    <div data-testid="macro-history" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="flex items-center justify-between mb-3">
        <SL>History</SL>
        <div className="flex gap-1">
          {ranges.map(r => (
            <button key={r.value} onClick={() => setHistoryRange(r.value)}
              className="px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all"
              style={{
                background: historyRange === r.value ? '#0f172a' : '#f1f5f9',
                color: historyRange === r.value ? '#fff' : '#64748b',
              }}>
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Regime color bar */}
      <div className="flex h-2 rounded-full overflow-hidden mb-2">
        {regimeSegments.map((s, i) => (
          <div key={i} style={{ flex: s.width, background: s.color, opacity: 0.3 }} />
        ))}
      </div>
      <div className="flex gap-3 mb-2">
        {Object.entries(REGIME_LABELS).map(([k, v]) => (
          <div key={k} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: REGIME_COLORS[k] }} />
            <span className="text-[10px]" style={{ color: '#94a3b8' }}>{v}</span>
          </div>
        ))}
      </div>

      {/* Interactive SVG chart */}
      <div className="relative">
        <svg ref={svgRef} viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 140 }}
          onMouseMove={handleMouseMove} onMouseLeave={handleMouseLeave}>
          {/* Regime background bands */}
          {regimeSegments.map((s, i) => (
            <rect key={i} x={s.x} y={0} width={s.width} height={h} fill={s.color} opacity={0.04} />
          ))}
          {/* Lines */}
          <path d={fgPath} fill="none" stroke="#d97706" strokeWidth="1.5" opacity="0.7" />
          <path d={roPath} fill="none" stroke="#dc2626" strokeWidth="1.5" opacity="0.7" />
          {/* Hover crosshair */}
          {hoverIdx !== null && (
            <>
              <line x1={hoverX} y1={0} x2={hoverX} y2={h} stroke="#94a3b8" strokeWidth="0.5" strokeDasharray="3,3" />
              <circle cx={hoverX} cy={getXY(hoverIdx, 'fearGreed', 0, 100).y} r="3" fill="#d97706" />
              <circle cx={hoverX} cy={getXY(hoverIdx, 'riskOffProb', 0, 1).y} r="3" fill="#dc2626" />
            </>
          )}
        </svg>

        {/* Hover tooltip card */}
        {hp && (
          <div className="absolute top-0 pointer-events-none z-10 rounded-lg px-3 py-2 shadow-lg"
            style={{
              left: `${Math.min(Math.max((hoverX / w) * 100, 10), 80)}%`,
              transform: 'translateX(-50%)',
              background: '#0f172a', color: '#e2e8f0', minWidth: 170,
            }}>
            <div className="text-[11px] font-bold mb-1" style={{ color: '#94a3b8' }}>{hoverDate}</div>
            <div className="flex items-center gap-2 mb-0.5">
              <div className="w-2 h-2 rounded-full" style={{ background: REGIME_COLORS[hp.regime] }} />
              <span className="text-[11px] font-semibold">{REGIME_LABELS[hp.regime] || hp.regime}</span>
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 mt-1">
              <span className="text-[10px]" style={{ color: '#94a3b8' }}>Fear&Greed</span>
              <span className="text-[11px] font-semibold tabular-nums" style={{ color: '#d97706' }}>{Math.round(hp.fearGreed)}</span>
              <span className="text-[10px]" style={{ color: '#94a3b8' }}>Risk-Off</span>
              <span className="text-[11px] font-semibold tabular-nums" style={{ color: '#dc2626' }}>{Math.round(hp.riskOffProb * 100)}%</span>
              <span className="text-[10px]" style={{ color: '#94a3b8' }}>CPI</span>
              <span className="text-[11px] font-semibold tabular-nums">{hp.cpi > 0 ? '+' : ''}{hp.cpi.toFixed(2)}</span>
              <span className="text-[10px]" style={{ color: '#94a3b8' }}>Confidence</span>
              <span className="text-[11px] font-semibold tabular-nums">{hp.macroMult.toFixed(2)}x</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-4 mt-1">
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-0.5 rounded" style={{ background: '#d97706' }} />
          <span className="text-[10px]" style={{ color: '#94a3b8' }}>Fear & Greed</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-4 h-0.5 rounded" style={{ background: '#dc2626' }} />
          <span className="text-[10px]" style={{ color: '#94a3b8' }}>Risk-Off Prob</span>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ REGIME TRANSITIONS ═══════════ */
function TransitionsPanel({ data }) {
  const t = data.transitions;
  if (!t || !t.probabilities) return null;

  const from = t.from;
  const fromColor = REGIME_COLORS[from] || '#94a3b8';
  const sorted = Object.entries(t.probabilities).sort((a, b) => b[1] - a[1]);

  const driftDir = t.cpiDrift > 0.1 ? 'BTC/stables' : t.cpiDrift < -0.1 ? 'alts' : 'flat';
  const momDir = t.riskoffMomentum > 0.02 ? 'increasing' : t.riskoffMomentum < -0.02 ? 'decreasing' : 'stable';

  return (
    <div data-testid="macro-transitions" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Regime Transitions</SL>
      <div className="text-[12px] mb-3" style={{ color: '#64748b' }}>
        From: <span className="font-bold" style={{ color: fromColor }}>{REGIME_LABELS[from] || from}</span>
      </div>

      <div className="space-y-2 mb-4">
        {sorted.map(([key, prob]) => {
          const pct = Math.round(prob * 100);
          const color = REGIME_COLORS[key] || '#94a3b8';
          const isSelf = key === from;
          return (
            <div key={key} data-testid={`macro-transition-${key}`} className="flex items-center gap-3">
              <ArrowRight className="w-3 h-3 shrink-0" style={{ color: isSelf ? '#94a3b8' : color }} />
              <span className="text-[12px] w-32 shrink-0" style={{ color: isSelf ? '#94a3b8' : '#334155', fontWeight: isSelf ? 400 : 600 }}>
                {isSelf ? 'Persistence' : ''} {REGIME_LABELS[key] || key}
              </span>
              <div className="flex-1 h-2 rounded-full" style={{ background: '#f1f5f9' }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color, opacity: isSelf ? 0.4 : 0.8 }} />
              </div>
              <span className="text-[13px] font-bold tabular-nums w-10 text-right" style={{ color }}>{pct}%</span>
            </div>
          );
        })}
      </div>

      <div className="flex gap-4 pt-2 border-t" style={{ borderColor: '#f1f5f9' }}>
        <div>
          <span className="text-[10px] uppercase" style={{ color: '#94a3b8' }}>CPI Drift</span>
          <div className="text-[12px] font-semibold tabular-nums" style={{ color: t.cpiDrift > 0 ? '#6366f1' : t.cpiDrift < 0 ? '#dc2626' : '#94a3b8' }}>
            {t.cpiDrift > 0 ? '+' : ''}{t.cpiDrift.toFixed(2)} ({driftDir})
          </div>
        </div>
        <div>
          <span className="text-[10px] uppercase" style={{ color: '#94a3b8' }}>Risk-Off Mom.</span>
          <div className="text-[12px] font-semibold tabular-nums" style={{ color: t.riskoffMomentum > 0 ? '#dc2626' : t.riskoffMomentum < 0 ? '#16a34a' : '#94a3b8' }}>
            {t.riskoffMomentum > 0 ? '+' : ''}{t.riskoffMomentum.toFixed(2)} ({momDir})
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ LIQUIDITY MIGRATION INDEX ═══════════ */
function LmiPanel({ data }) {
  const lmi = data.lmi;
  if (!lmi) return null;

  const val = lmi.lmi;
  const color = lmi.state === 'INFLOW_TO_SAFETY' ? '#dc2626' : lmi.state === 'OUTFLOW_FROM_SAFETY' ? '#16a34a' : '#94a3b8';
  const stateLabel = lmi.state.replace(/_/g, ' ');
  const tip = lmi.state === 'INFLOW_TO_SAFETY'
    ? 'Liquidity flowing to BTC/stables. Alts losing capital — reduce alt exposure'
    : lmi.state === 'OUTFLOW_FROM_SAFETY'
    ? 'Liquidity leaving safety. Capital deploying to risk assets — alts benefit'
    : 'Liquidity balanced. No strong directional migration';

  // Bar visualization: -100 to +100 mapped to 0..100%
  const barPct = 50 + (val / 2);

  return (
    <div data-testid="macro-lmi" className="rounded-2xl p-5" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Liquidity Migration</SL>
      <Tip text={tip}>
        <div className="flex items-baseline gap-3 mb-2">
          <span className="text-[26px] font-bold tabular-nums" style={{ color }}>{val > 0 ? '+' : ''}{val}</span>
          <span className="text-[12px] font-bold uppercase" style={{ color }}>{stateLabel}</span>
        </div>
      </Tip>

      {/* Bar: center = 0, left = -100, right = +100 */}
      <div className="relative h-3 rounded-full mb-3" style={{ background: '#f1f5f9' }}>
        <div className="absolute top-0 left-1/2 w-px h-full" style={{ background: '#cbd5e1' }} />
        {val >= 0 ? (
          <div className="absolute h-full rounded-r-full" style={{ left: '50%', width: `${(val / 100) * 50}%`, background: color, opacity: 0.6 }} />
        ) : (
          <div className="absolute h-full rounded-l-full" style={{ right: '50%', width: `${(-val / 100) * 50}%`, background: color, opacity: 0.6 }} />
        )}
      </div>

      <div className="flex gap-4">
        <div>
          <span className="text-[10px] uppercase" style={{ color: '#94a3b8' }}>BTC Dom shift</span>
          <div className="text-[13px] font-semibold tabular-nums" style={{ color: lmi.deltaBtcDom7d > 0 ? '#6366f1' : lmi.deltaBtcDom7d < 0 ? '#dc2626' : '#94a3b8' }}>
            {lmi.deltaBtcDom7d > 0 ? '+' : ''}{lmi.deltaBtcDom7d}%
          </div>
        </div>
        <div>
          <span className="text-[10px] uppercase" style={{ color: '#94a3b8' }}>Stable Dom shift</span>
          <div className="text-[13px] font-semibold tabular-nums" style={{ color: lmi.deltaStableDom7d > 0.1 ? '#d97706' : lmi.deltaStableDom7d < -0.1 ? '#16a34a' : '#94a3b8' }}>
            {lmi.deltaStableDom7d > 0 ? '+' : ''}{lmi.deltaStableDom7d}%
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ RISK SPLIT (Structural vs Tactical) ═══════════ */
function RiskSplitPanel({ data }) {
  const rs = data.riskSplit;
  if (!rs) return null;

  const levelColor = (level) => {
    if (level === 'EXTREME') return '#dc2626';
    if (level === 'HIGH') return '#f97316';
    if (level === 'MEDIUM') return '#d97706';
    return '#16a34a';
  };

  const rows = [
    { key: 'structural', label: 'Structural Risk', value: rs.structural, level: rs.levels?.structural,
      tip: 'Macro-level risk: capital flows, regime instability, risk-off probability. Affects medium/long-term positioning' },
    { key: 'tactical', label: 'Tactical Risk', value: rs.tactical, level: rs.levels?.tactical,
      tip: 'Exchange microstructure risk: volatility, liquidity, funding. Affects short-term entries and sizing' },
    { key: 'total', label: 'Total Risk', value: rs.total, level: rs.levels?.total,
      tip: 'Combined risk (55% tactical + 45% structural). Overall risk posture for position management' },
  ];

  return (
    <div data-testid="macro-risk-split" className="rounded-2xl p-4 h-full" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Risk Decomposition</SL>
      <div className="space-y-3">
        {rows.map(r => {
          const c = levelColor(r.level);
          return (
            <Tip key={r.key} text={r.tip} block>
              <div data-testid={`macro-risk-${r.key}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] font-medium" style={{ color: '#64748b' }}>{r.label}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[15px] font-bold tabular-nums" style={{ color: c }}>{r.value}</span>
                    <span className="text-[10px] font-bold" style={{ color: c }}>{r.level}</span>
                  </div>
                </div>
                <div className="h-2 rounded-full" style={{ background: '#f1f5f9' }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${r.value}%`, background: c, opacity: r.key === 'total' ? 0.8 : 0.5 }} />
                </div>
              </div>
            </Tip>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════ BTC ↔ SPX Hybrid Layer ═══════════ */
const REGIME_C = { RISK_ON: '#16a34a', RISK_OFF: '#dc2626', NEUTRAL: '#d97706', UNKNOWN: '#94a3b8' };
const DIV_C = { BTC_OUTPERFORMS: '#16a34a', BTC_UNDERPERFORMS: '#dc2626', NEUTRAL: '#94a3b8' };
const DIV_LABELS = { BTC_OUTPERFORMS: 'BTC Outperforms', BTC_UNDERPERFORMS: 'BTC Underperforms', NEUTRAL: 'Neutral' };
const SPX_LABELS = { RISK_ON: 'Risk-On', RISK_OFF: 'Risk-Off', NEUTRAL: 'Neutral', UNKNOWN: '—' };

function HybridLayerPanel({ hybridData, macroData }) {
  if (!hybridData) return null;
  const { correlation30d, beta, spxRegime, divergenceScore, divergenceState, hybridImpact, meta } = hybridData;
  const impactColor = hybridImpact > 0.02 ? '#16a34a' : hybridImpact < -0.02 ? '#dc2626' : '#94a3b8';
  const corrColor = correlation30d > 0.5 ? '#16a34a' : correlation30d > 0.2 ? '#d97706' : correlation30d < -0.2 ? '#dc2626' : '#94a3b8';

  // Execution narrative from macro data
  const c = macroData?.computed || {};
  const regime = REGIME_LABELS[c.regime] || c.regime || '—';
  const isBlocked = c.strongActionsBlocked;

  return (
    <div data-testid="hybrid-layer-panel" className="rounded-2xl p-4 h-full flex flex-col" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-[11px] uppercase tracking-wider font-semibold" style={{ color: '#94a3b8' }}>BTC ↔ SPX Hybrid Layer</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold" style={{ color: '#475569' }}>
            Macro: {regime}
          </span>
          <span className="text-[10px] font-semibold"
            style={{ color: isBlocked ? '#dc2626' : '#16a34a' }}>
            {isBlocked ? 'RISK-OFF RESTRICTED' : 'EXECUTION ENABLED'}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3 flex-1">
        {/* Col 1: Correlation */}
        <div>
          <div className="text-[10px] mb-0.5" style={{ color: '#94a3b8' }}>Correlation (30d)</div>
          <div className="text-[18px] font-black tabular-nums" style={{ color: corrColor }}>
            {correlation30d > 0 ? '+' : ''}{correlation30d.toFixed(2)}
          </div>
          <div className="text-[10px]" style={{ color: '#94a3b8' }}>
            {correlation30d > 0.5 ? 'Strongly correlated' : correlation30d > 0.2 ? 'Moderate' : 'Weak'}
          </div>
        </div>

        {/* Col 2: Beta + SPX Regime */}
        <div>
          <div className="text-[10px] mb-0.5" style={{ color: '#94a3b8' }}>Beta to SPX</div>
          <div className="text-[18px] font-black tabular-nums" style={{ color: '#0f172a' }}>
            {beta.toFixed(2)}
          </div>
          <span data-testid="spx-regime-badge" className="inline-block text-[10px] font-bold"
            style={{ color: REGIME_C[spxRegime] || '#94a3b8' }}>
            SPX: {SPX_LABELS[spxRegime] || spxRegime}
          </span>
        </div>

        {/* Col 3: Divergence */}
        <div>
          <div className="text-[10px] mb-0.5" style={{ color: '#94a3b8' }}>Divergence</div>
          <span className="inline-block text-[10px] font-bold"
            style={{ color: DIV_C[divergenceState] || '#94a3b8' }}>
            {DIV_LABELS[divergenceState] || divergenceState}
          </span>
          {meta && (
            <div className="text-[10px] mt-1" style={{ color: '#94a3b8' }}>
              BTC 7d: {meta.btc7dReturn > 0 ? '+' : ''}{meta.btc7dReturn}%<br/>
              SPX 7d: {meta.spx7dReturn > 0 ? '+' : ''}{meta.spx7dReturn}%
            </div>
          )}
        </div>

        {/* Col 4: Hybrid Impact */}
        <div className="flex flex-col items-end">
          <div className="text-[10px] mb-0.5" style={{ color: '#94a3b8' }}>Hybrid Impact</div>
          <div data-testid="hybrid-impact-value" className="text-[22px] font-black tabular-nums leading-none" style={{ color: impactColor }}>
            {hybridImpact > 0 ? '+' : ''}{hybridImpact.toFixed(3)}
          </div>
          <div className="text-[10px] mt-0.5" style={{ color: '#94a3b8' }}>
            {Math.abs(hybridImpact) < 0.03 ? 'Negligible' : hybridImpact > 0 ? 'Confidence boost' : 'Confidence drag'}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ Position Policy Panel (compact for Macro page) ═══════════ */
const POS_MODE_C = { DEFENSIVE: '#d97706', NEUTRAL: '#94a3b8', AGGRESSIVE: '#16a34a' };

function PositionPolicyPanel({ posData }) {
  if (!posData?.ok) return null;
  const { sizeMult, mode, blocked, explain, blockedReasons, inputs } = posData;
  const mc = POS_MODE_C[mode] || '#94a3b8';

  return (
    <div data-testid="macro-position-policy-panel" className="rounded-2xl p-4 h-full flex flex-col" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="text-[11px] uppercase tracking-wider font-semibold mb-2" style={{ color: '#94a3b8' }}>Position Policy</div>
      <div className="flex items-center gap-2 mb-2">
        <span data-testid="macro-position-size-value" className="text-[22px] font-black tabular-nums leading-none"
          style={{ color: blocked ? '#dc2626' : mc }}>
          {blocked ? '0.00' : sizeMult.toFixed(2)}
          <span className="text-[11px] font-bold ml-0.5">x</span>
        </span>
        <div className="flex flex-col gap-0.5">
          <span data-testid="macro-position-mode" className="text-[9px] font-bold tracking-wide"
            style={{ color: mc }}>{mode}</span>
          {blocked && (
            <span className="text-[9px] font-bold tracking-wide" style={{ color: '#dc2626' }}>
              BLOCKED
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 flex flex-col gap-0.5">
        {(blocked ? blockedReasons : explain)?.slice(0, 2).map((r, i) => (
          <div key={i} className="text-[10px] leading-tight" style={{ color: blocked ? '#dc2626' : '#64748b' }}>{r}</div>
        ))}
      </div>
      {inputs && (
        <div className="text-[9px] mt-1" style={{ color: '#94a3b8' }}>
          {inputs.core.direction} · S{inputs.risk.structural}/T{inputs.risk.tactical} · {inputs.sync.state}
        </div>
      )}
    </div>
  );
}

/* ═══════════ MAIN PAGE ═══════════ */
export default function MacroV2Page() {
  const [data, setData] = useState(null);
  const [history, setHistory] = useState(null);
  const [posData, setPosData] = useState(null);
  const [hybridData, setHybridData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [historyRange, setHistoryRange] = useState(30);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const snapRes = await fetch(`${API}/api/core/macro/snapshot`);
      if (!snapRes.ok) throw new Error(`Snapshot: ${snapRes.status}`);
      const snap = await snapRes.json();
      if (mountedRef.current) setData(snap);

      // History, position sizing, hybrid — non-blocking, staggered to avoid 429
      setTimeout(() => {
        fetch(`${API}/api/core/macro/history?limit=90`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (mountedRef.current && d) setHistory(d); })
          .catch(() => {});
      }, 200);

      setTimeout(() => {
        fetch(`${API}/api/core/position-size?asset=BTCUSDT&tf=1h`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (mountedRef.current && d) setPosData(d); })
          .catch(() => {});
      }, 500);

      setTimeout(() => {
        fetch(`${API}/api/core/hybrid-layer`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (mountedRef.current && d) setHybridData(d); })
          .catch(() => {});
      }, 800);
    } catch (e) {
      console.error('Macro V2 fetch error:', e);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    const iv = setInterval(fetchData, 120000);
    return () => { mountedRef.current = false; clearInterval(iv); };
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64" data-testid="macro-v2-loading">
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: '#94a3b8' }} />
      </div>
    );
  }

  if (!data?.ok) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="text-[14px]" style={{ color: '#dc2626' }}>Failed to load Macro data</span>
      </div>
    );
  }

  return (
    <div className="max-w-[1600px] mx-auto px-6 py-4" data-testid="macro-v2-page">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-[22px] font-bold" style={{ color: '#0f172a' }}>Capital Flow Engine</h1>
          <span className="text-[12px]" style={{ color: '#94a3b8' }}>
            Market-level capital allocation and regime detection model
          </span>
        </div>
        <button onClick={fetchData} data-testid="macro-refresh-btn"
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-all hover:bg-gray-100"
          style={{ color: '#64748b' }}>
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Row 1: Overview + Market Context */}
      <div className="grid grid-cols-2 gap-5 mb-5">
        <MacroOverview data={data} />
        <MarketContext data={data} />
      </div>

      {/* Row 2: Capital Flow Map (left 2/3) + LMI (right 1/3) */}
      <div className="grid grid-cols-3 gap-5 mb-5">
        <div className="col-span-2"><CapitalFlowMap data={data} /></div>
        <LmiPanel data={data} />
      </div>

      {/* Row 3: Hybrid Layer + Position Policy (left 2/3) + Risk Decomposition (right 1/3) */}
      <div className="grid grid-cols-3 gap-5 mb-5 items-stretch">
        <div className="col-span-2 flex gap-5 h-full">
          <div className="flex-1 h-full"><HybridLayerPanel hybridData={hybridData} macroData={data} /></div>
          <div className="w-[220px] shrink-0 h-full"><PositionPolicyPanel posData={posData} /></div>
        </div>
        <RiskSplitPanel data={data} />
      </div>

      {/* Row 3: Regime Grid + Impact */}
      <div className="grid grid-cols-2 gap-5 mb-5">
        <RegimeGrid data={data} />
        <ImpactPanel data={data} />
      </div>

      {/* Row 4: Transitions + Drivers */}
      <div className="grid grid-cols-2 gap-5 mb-5">
        <TransitionsPanel data={data} />
        <DriversPanel data={data} />
      </div>

      {/* Row 5: History */}
      <div>
        <HistoryPanel historyData={history} historyRange={historyRange} setHistoryRange={setHistoryRange} />
      </div>
    </div>
  );
}
