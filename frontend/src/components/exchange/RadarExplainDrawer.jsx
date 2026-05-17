/**
 * Radar Explain Drawer V4 — Multi-Horizon breakdown + Tier badge
 */
import React from 'react';
import { ChevronUp, ChevronDown, Minus } from 'lucide-react';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from '../../components/ui/sheet';

const VERDICT_COLORS = {
  buy: '#16a34a',
  sell: '#dc2626',
  watch: '#f59e0b',
  neutral: '#64748b',
  data_gap: '#a1a1aa',
};

const DRIVER_LABELS = {
  compression: 'Compression',
  volumeBuild: 'Volume build-up',
  trendAlignment: 'Trend alignment',
  liquidity: 'Liquidity',
  risk: 'Risk',
  oiShift: 'OI shift',
  fundingSkew: 'Funding skew',
  liquidationDensity: 'Liquidation density',
  volatilityRegime: 'Volatility regime',
};

const TIER_STYLES = {
  'A+': { bg: '#dcfce7', color: '#15803d', border: '#bbf7d0' },
  'A':  { bg: '#d1fae5', color: '#059669', border: '#a7f3d0' },
  'B':  { bg: '#fef3c7', color: '#b45309', border: '#fde68a' },
  'C':  { bg: '#f1f5f9', color: '#64748b', border: '#e2e8f0' },
  'noise': { bg: '#f8fafc', color: '#94a3b8', border: '#e2e8f0' },
};

const HORIZON_META = {
  short: { label: 'Short (0\u20132d)', color: '#dc2626' },
  mid:   { label: 'Mid (3\u20137d)', color: '#d97706' },
  swing: { label: 'Swing (1\u20134w)', color: '#7c3aed' },
};

function DirIcon({ dir }) {
  const cls = 'w-4 h-4 inline';
  if (dir === 'long') return <ChevronUp className={cls} style={{ color: '#16a34a' }} />;
  if (dir === 'short') return <ChevronDown className={cls} style={{ color: '#dc2626' }} />;
  return <Minus className={cls} style={{ color: '#94a3b8' }} />;
}

function DriverBar({ value, color }) {
  const pct = Math.min(100, Math.abs(value) * 100);
  return (
    <div className="flex-1 h-1 rounded bg-[rgba(15,23,42,0.08)] overflow-hidden">
      <div
        className="h-full rounded transition-all duration-300"
        style={{ width: `${pct}%`, backgroundColor: color }}
      />
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <h4 className="text-[12px] font-medium uppercase tracking-[1px] text-slate-400 mt-6 mb-2">
      {children}
    </h4>
  );
}

function HorizonBreakdown({ horizons }) {
  if (!horizons) return null;

  const items = ['short', 'mid', 'swing'].map(key => {
    const h = horizons[key];
    if (!h) return null;
    const meta = HORIZON_META[key];
    const isPrimary = horizons.primary === key;
    return { key, h, meta, isPrimary };
  }).filter(Boolean);

  if (!items.length) return null;

  return (
    <>
      <SectionTitle>Multi-Horizon</SectionTitle>
      <div data-testid="explain-horizons" className="space-y-2">
        {items.map(({ key, h, meta, isPrimary }) => (
          <div
            key={key}
            className="flex items-center gap-3 py-2 px-3 rounded-lg"
            style={{
              background: 'transparent',
            }}
          >
            {/* Horizon label */}
            <span
              className="text-[12px] font-semibold w-24 flex-shrink-0"
              style={{ color: meta.color }}
            >
              {meta.label}
              {isPrimary && (
                <span className="ml-1 text-[10px] font-bold opacity-60">★</span>
              )}
            </span>

            {/* Direction */}
            <span className="text-[13px] font-medium capitalize w-12 flex-shrink-0"
              style={{ color: (h.direction || h.dir) === 'long' ? '#16a34a' : (h.direction || h.dir) === 'short' ? '#dc2626' : '#94a3b8' }}
            >
              {h.direction || h.dir || '\u2013'}
            </span>

            {/* Conviction bar */}
            <div className="flex-1 flex items-center gap-2">
              <div className="flex-1 h-1.5 rounded-sm overflow-hidden" style={{ background: 'rgba(15,23,42,0.06)' }}>
                <div
                  className="h-full rounded-sm transition-all duration-300"
                  style={{ width: `${h.conviction ?? 0}%`, backgroundColor: meta.color }}
                />
              </div>
              <span className="text-[13px] font-bold tabular-nums w-8 text-right" style={{ color: '#0f172a' }}>
                {h.conviction ?? 0}
              </span>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default function RadarExplainDrawer({ row, open, onClose }) {
  if (!row) return null;

  const verdictColor = VERDICT_COLORS[row.verdict] || '#64748b';
  const dirColor = row.direction === 'long' ? '#16a34a' : row.direction === 'short' ? '#dc2626' : '#94a3b8';
  const isFutures = row.mode === 'futures';
  const isGap = row.verdict === 'data_gap';
  const tier = row.convictionTier;
  const tierStyle = tier ? (TIER_STYLES[tier] || TIER_STYLES['C']) : null;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent
        className="w-[480px] sm:w-[520px] overflow-y-auto bg-white border-l border-slate-100"
        style={{ padding: '24px' }}
        data-testid="radar-explain-drawer"
      >
        <SheetHeader className="pb-0">
          <SheetTitle className="flex flex-col gap-1">
            {/* Symbol */}
            <span className="text-[20px] font-semibold text-slate-900">
              {row.symbol.replace('USDT', '')}
            </span>

            {/* Verdict + Direction + Tier */}
            <div className="flex items-center gap-2">
              <span className="text-[14px] font-semibold uppercase" style={{ color: verdictColor }}>
                {isGap ? 'DATA GAP' : row.verdict}
              </span>
              {!isGap && (
                <>
                  <span className="text-slate-300">{'\u00b7'}</span>
                  <span className="flex items-center gap-0.5 text-[14px] font-semibold capitalize" style={{ color: dirColor }}>
                    <DirIcon dir={row.direction} />
                    {row.direction}
                  </span>
                </>
              )}
              {tierStyle && (
                <>
                  <span className="text-slate-300">{'\u00b7'}</span>
                  <span
                    data-testid="drawer-tier-badge"
                    className="text-[12px] font-semibold"
                    style={{ color: tierStyle.color }}
                  >
                    Tier {tier}
                  </span>
                </>
              )}
            </div>

            {isGap ? (
              <div className="mt-2 p-3 rounded-lg" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                <p className="text-[13px] text-slate-500">
                  Insufficient market data to compute a reliable setup for this asset.
                </p>
                {row.dataQuality?.missing?.length > 0 && (
                  <p className="text-[11px] text-slate-400 mt-1">
                    Missing: {row.dataQuality.missing.join(', ')}
                  </p>
                )}
              </div>
            ) : (
              <>
                {/* Conviction */}
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-[11px] uppercase tracking-wider text-slate-400">Conviction</span>
                  <span className="text-[18px] font-bold tabular-nums" style={{ color: row.conviction >= 60 ? verdictColor : '#0f172a' }}>
                    {row.conviction}
                  </span>
                  {row.conviction >= 60 && (
                    <span className="text-[10px] font-semibold uppercase"
                      style={{ color: verdictColor, letterSpacing: '0.5px' }}>
                      High conviction
                    </span>
                  )}
                </div>

                {/* Horizon */}
                {row.explain?.timeHorizon && (
                  <span className="text-[13px] text-slate-500 mt-0.5">
                    Horizon: {row.explain.timeHorizon}
                  </span>
                )}
              </>
            )}
          </SheetTitle>
        </SheetHeader>

        {!isGap && (
          <>
            {/* Multi-Horizon Breakdown */}
            <HorizonBreakdown horizons={row.horizons} />

            {/* Why Now */}
            <SectionTitle>Why now</SectionTitle>
            <div data-testid="explain-why-now">
              {(row.reasons?.length > 0 ? row.reasons : [row.explain?.whyNow || 'No active catalysts']).map((r, i) => (
                <div key={i} className="flex items-start gap-2 py-0.5">
                  <span className="text-slate-300 mt-0.5 text-[13px]">{'\u00b7'}</span>
                  <span className="text-[13px] text-slate-700 leading-relaxed">{r}</span>
                </div>
              ))}
            </div>

            {/* Plan */}
            <SectionTitle>Plan</SectionTitle>
            <div data-testid="explain-plan" className="space-y-1.5">
              <div className="flex items-start gap-2">
                <span className="text-[12px] text-slate-400 w-20 flex-shrink-0">Invalidation</span>
                <span className="text-[13px] text-slate-700">{row.explain?.invalidation || 'N/A'}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[12px] text-slate-400 w-20 flex-shrink-0">Horizon</span>
                <span className="text-[13px] text-slate-700">{row.explain?.timeHorizon || '24h'}</span>
              </div>
            </div>

            {/* Drivers */}
            <SectionTitle>Drivers</SectionTitle>
            <div data-testid="explain-drivers" className="space-y-0">
              {/* Support both array format (Radar) and object format (Market Board) */}
              {(Array.isArray(row.features)
                ? row.features
                : Object.entries(row.features || {}).map(([key, value]) => ({ key, value }))
              ).map(f => {
                const label = DRIVER_LABELS[f.key] || f.label || f.key;
                const isNeg = f.key === 'fundingSkew';
                const displayVal = isNeg ? f.value.toFixed(2) : `${(f.value * 100).toFixed(0)}%`;
                return (
                  <div key={f.key} className="flex items-center gap-3 py-1.5">
                    <span className="text-[12px] text-slate-500 w-32 flex-shrink-0 truncate">{label}</span>
                    <DriverBar value={f.value} color={verdictColor} />
                    <span className="text-[12px] tabular-nums text-slate-600 w-10 text-right">{displayVal}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}

        {/* Venue tag */}
        <div className="mt-6 flex items-center gap-2 flex-wrap">
          <span className="text-[11px] text-slate-400 font-medium">
            {isFutures ? 'Futures' : row.venue === 'alpha' ? 'Spot Alpha' : 'Spot Main'}
          </span>
          {(row.venueCount ?? 1) >= 2 && (
            <span className="text-[11px] font-medium" style={{ color: '#6366f1' }}>
              {row.venueCount}V
            </span>
          )}
          {isFutures && row.squeezeRisk === 'high' && (
            <span className="text-[11px] text-red-500 font-medium">
              Squeeze risk
            </span>
          )}
        </div>

        {/* P1.2: Divergence section */}
        {(row.divergenceScore ?? 0) >= 0.25 && (row.venueCount ?? 1) >= 2 && (
          <div data-testid="explain-divergence" className="mt-4">
            <SectionTitle>Venue Divergence</SectionTitle>
            <div className="p-3 rounded-lg" style={{
              background: row.divergenceLabel === 'HIGH' ? 'rgba(220,38,38,0.04)' : 'rgba(217,119,6,0.04)',
              border: `1px solid ${row.divergenceLabel === 'HIGH' ? 'rgba(220,38,38,0.12)' : 'rgba(217,119,6,0.12)'}`,
            }}>
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className="text-[11px] font-bold"
                  style={{
                    color: row.divergenceLabel === 'HIGH' ? '#dc2626' : '#b45309',
                  }}
                >
                  {row.divergenceLabel}
                </span>
                <span className="text-[13px] font-bold tabular-nums" style={{ color: '#0f172a' }}>
                  {((row.divergenceScore ?? 0) * 100).toFixed(0)}%
                </span>
              </div>
              {(row.divergenceReasons || []).map((r, i) => (
                <div key={i} className="flex items-start gap-2 py-0.5">
                  <span className="text-slate-300 mt-0.5 text-[13px]">{'\u00b7'}</span>
                  <span className="text-[13px] text-slate-600">{r}</span>
                </div>
              ))}
              <span className="text-[11px] text-slate-400 mt-1.5 block">Short-horizon conviction boost applied</span>
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
