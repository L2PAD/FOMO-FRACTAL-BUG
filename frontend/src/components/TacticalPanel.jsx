/**
 * Tactical Panel — Block X.C — Decision Enhancer
 * ================================================
 * Shows tactical microstructure conditions (1D) AND what they change in execution.
 * Not "another signal" — a context layer that enhances the FINAL DECISION.
 *
 * Architecture: Forecast → Context → **Tactical** → Drift → Execution
 */

import { TrendingUp, TrendingDown, Minus, ArrowRight, Crosshair } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const BIAS_CONFIG = {
  bearish: { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'BEARISH', icon: TrendingDown },
  bullish: { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'BULLISH', icon: TrendingUp },
  neutral: { color: '#64748b', bg: '#f8fafc', border: '#e2e8f0', label: 'NEUTRAL', icon: Minus },
};

const ADVICE_CONFIG = {
  wait:              { color: '#dc2626', bg: '#fef2f2', label: 'WAIT' },
  reduced:           { color: '#d97706', bg: '#fffbeb', label: 'REDUCE' },
  avoid_aggressive:  { color: '#ea580c', bg: '#fff7ed', label: 'CAUTIOUS' },
  normal:            { color: '#16a34a', bg: '#f0fdf4', label: 'NORMAL' },
};

export default function TacticalPanel({ data }) {
  if (!data) return null;

  const bias = data.tacticalBias || 'neutral';
  const bc = BIAS_CONFIG[bias] || BIAS_CONFIG.neutral;
  const BiasIcon = bc.icon;
  const advice = data.executionAdvice || 'normal';
  const ac = ADVICE_CONFIG[advice] || ADVICE_CONFIG.normal;
  const quality = data.tradeQuality || 'medium';
  const signals = data.signals || {};
  const impact = data.executionImpact || {};
  const strength = Math.round((data.signalStrength || 0) * 100);
  const sizePct = impact.sizePct || 100;

  // Active signals
  const activeSignals = [];
  if (signals.orderflow?.bearish)         activeSignals.push({ label: 'Order Flow Imbalance', type: 'bearish' });
  if (signals.orderflow?.bullish)         activeSignals.push({ label: 'Order Flow Bullish', type: 'bullish' });
  if (signals.liquidations?.forcedSelling) activeSignals.push({ label: 'Liquidation Pressure', type: 'bearish' });
  if (signals.liquidations?.forcedBuying)  activeSignals.push({ label: 'Short Squeeze', type: 'bullish' });
  if (signals.funding?.crowdedLongs)       activeSignals.push({ label: 'Funding Extreme (Longs)', type: 'bearish' });
  if (signals.funding?.crowdedShorts)      activeSignals.push({ label: 'Funding Extreme (Shorts)', type: 'bullish' });
  if (signals.absorption?.sellerExhaustion) activeSignals.push({ label: 'Seller Exhaustion', type: 'bullish' });
  if (signals.absorption?.buyerExhaustion)  activeSignals.push({ label: 'Buyer Exhaustion', type: 'bearish' });

  return (
    <div className="rounded-2xl overflow-hidden"
      data-testid="tactical-panel"
      style={{ background: bc.bg, border: `1.5px solid ${bc.border}` }}>

      {/* Header */}
      <div className="flex items-center gap-2 px-5 pt-4 pb-3">
        <Crosshair className="w-4 h-4" style={{ color: '#64748b' }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a', letterSpacing: '0.02em', textTransform: 'uppercase' }}>
          Tactical Conditions
        </span>
        <span className="ml-auto" style={{ fontSize: 10, color: '#94a3b8', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
          1D Decision Enhancer
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-0">
        {/* ── Col 1: Bias + Confidence ── */}
        <div className="md:col-span-3 px-5 pb-4" style={{ borderRight: '1px solid rgba(226,232,240,0.5)' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: bias === 'bearish' ? '#fee2e2' : bias === 'bullish' ? '#dcfce7' : '#f1f5f9' }}>
              <BiasIcon className="w-5 h-5" style={{ color: bc.color }} />
            </div>
            <div>
              <div style={{ fontSize: 10, color: '#94a3b8', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Tactical Bias</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: bc.color, letterSpacing: '-0.01em' }}>{bc.label}</div>
            </div>
          </div>

          <div className="mt-3">
            <div className="flex items-center justify-between">
              <span style={{ fontSize: 11, color: '#94a3b8' }}>Confidence</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: strength > 40 ? '#0f172a' : '#94a3b8' }}>{strength}%</span>
            </div>
            <div className="mt-1 h-1 rounded-full" style={{ background: '#e2e8f0' }}>
              <div className="h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.max(strength, 3)}%`, background: bc.color }} />
            </div>

            <div className="flex items-center gap-2 mt-2.5">
              <span className="px-2 py-0.5 rounded text-xs font-bold"
                style={{ color: ac.color, background: ac.bg, fontSize: 10 }}>
                {ac.label}
              </span>
              <span style={{ fontSize: 10, color: '#94a3b8' }} className="capitalize">{quality} quality</span>
            </div>
          </div>
        </div>

        {/* ── Col 2: Active Signals ── */}
        <div className="md:col-span-3 px-5 pb-4" data-testid="tactical-signals" style={{ borderRight: '1px solid rgba(226,232,240,0.5)' }}>
          <div style={{ fontSize: 10, color: '#94a3b8', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 8 }}>Signals</div>
          {activeSignals.length > 0 ? (
            <div className="space-y-1.5">
              {activeSignals.map((s, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: s.type === 'bearish' ? '#dc2626' : '#16a34a' }} />
                  <span style={{ fontSize: 12, color: '#475569' }}>{s.label}</span>
                </div>
              ))}
            </div>
          ) : (
            <span style={{ fontSize: 12, color: '#cbd5e1' }}>No strong signals</span>
          )}
        </div>

        {/* ── Col 3: Execution Impact (widest — most important) ── */}
        <div className="md:col-span-6 px-5 pb-4" data-testid="tactical-impact">
          <div className="flex items-center justify-between" style={{ marginBottom: 8 }}>
            <span style={{ fontSize: 10, color: '#94a3b8', letterSpacing: '0.05em', textTransform: 'uppercase' }}>Impact on Execution</span>
            {sizePct < 100 && (
              <span className="px-1.5 py-0.5 rounded font-bold"
                style={{ fontSize: 10, color: '#d97706', background: '#fffbeb' }}>
                Size {sizePct}%
              </span>
            )}
          </div>

          <div className="space-y-1.5">
            {(impact.impacts || []).map((imp, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <ArrowRight className="w-3 h-3 mt-0.5 flex-shrink-0" style={{ color: i === 0 ? '#475569' : '#94a3b8' }} />
                <span style={{ fontSize: 12, color: i === 0 ? '#0f172a' : '#475569', fontWeight: i === 0 ? 600 : 400 }}>
                  {imp}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-3 pt-2" style={{ borderTop: '1px solid rgba(226,232,240,0.4)' }}>
            <span style={{ fontSize: 10, color: '#cbd5e1', fontStyle: 'italic' }}>
              {impact.note || 'Enhances execution — does not override strategic forecast'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Hook to fetch tactical data
 */
export function useTacticalData() {
  const { useState, useEffect, useCallback } = require('react');
  const [tactical, setTactical] = useState(null);

  const fetchTactical = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/tactical/1d?asset=BTC`);
      const json = await res.json();
      if (json.ok) setTactical(json);
    } catch {}
  }, []);

  useEffect(() => {
    fetchTactical();
    const iv = setInterval(fetchTactical, 60000);
    return () => clearInterval(iv);
  }, [fetchTactical]);

  return { tactical, fetchTactical };
}
