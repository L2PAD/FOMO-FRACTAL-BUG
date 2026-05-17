/**
 * Block 5: Model Health & Drift — institutional dashboard
 * Sections: Performance (per horizon) + Drift Status + ML Weight + Drivers + Calibration
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, Activity, AlertTriangle, CheckCircle2, Shield, ChevronDown, ChevronUp } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

function RingGauge({ value, max = 1, size = 48, color }) {
  const pct = Math.min(1, Math.max(0, value / max));
  const r = (size - 6) / 2;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - pct);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#e2e8f0" strokeWidth={3.5} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={3.5}
        strokeLinecap="round" strokeDasharray={circumference} strokeDashoffset={offset}
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      <text x={size/2} y={size/2} textAnchor="middle" dominantBaseline="central"
        fill={color} fontSize={11} fontWeight={700}>{Math.round(pct * 100)}%</text>
    </svg>
  );
}

function DriftBar({ value, max = 1, status }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const colors = { OK: '#16a34a', WATCH: '#d97706', DRIFT: '#dc2626' };
  const bg = colors[status] || '#3b82f6';
  return (
    <div className="w-full h-2 rounded-full" style={{ background: '#f1f5f9' }}>
      <div className="h-full rounded-full" style={{
        width: `${pct}%`, background: bg,
        transition: 'width 0.8s ease, background 0.4s ease',
        minWidth: value > 0 ? 4 : 0,
      }} />
    </div>
  );
}

const STATUS_COLORS = {
  OK: { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0' },
  WATCH: { bg: '#fffbeb', text: '#d97706', border: '#fde68a' },
  DRIFT: { bg: '#fef2f2', text: '#dc2626', border: '#fecaca' },
};

const STATUS_LABELS = { OK: 'Stable', WATCH: 'Watch', DRIFT: 'Drift' };

export default function ModelHealthPanel({ asset = 'BTC' }) {
  const [health, setHealth] = useState(null);
  const [drift7D, setDrift7D] = useState(null);
  const [drift30D, setDrift30D] = useState(null);
  const [loading, setLoading] = useState(true);
  const [driftExpanded, setDriftExpanded] = useState(false);
  const [driftHistory, setDriftHistory] = useState({ '7D': [], '30D': [] });
  const [shadowVerdict, setShadowVerdict] = useState(null);
  const [pruning, setPruning] = useState(null);
  const [graduation, setGraduation] = useState(null);
  const [calibration, setCalibration] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [hRes, d7Res, d30Res, hist7Res, hist30Res, verdictRes] = await Promise.all([
        fetch(`${API}/api/prediction/exchange/model-health?asset=${asset}`),
        fetch(`${API}/api/drift/status?horizon=7D&asset=${asset}`),
        fetch(`${API}/api/drift/status?horizon=30D&asset=${asset}`),
        fetch(`${API}/api/drift/history/chart?horizon=7D&asset=${asset}&days=45`),
        fetch(`${API}/api/drift/history/chart?horizon=30D&asset=${asset}&days=45`),
        fetch(`${API}/api/ml-overlay/status`),
      ]);
      const [hJson, d7Json, d30Json, h7Json, h30Json, vJson] = await Promise.all([
        hRes.ok ? hRes.json() : null,
        d7Res.ok ? d7Res.json() : null,
        d30Res.ok ? d30Res.json() : null,
        hist7Res.ok ? hist7Res.json() : null,
        hist30Res.ok ? hist30Res.json() : null,
        verdictRes.ok ? verdictRes.json() : null,
      ]);
      if (hJson?.ok) setHealth(hJson);
      if (d7Json?.ok) setDrift7D(d7Json);
      if (d30Json?.ok) setDrift30D(d30Json);
      setDriftHistory({
        '7D': h7Json?.data || [],
        '30D': h30Json?.data || [],
      });
      if (vJson?.ok) {
        setShadowVerdict(vJson.evalSummary);
        if (vJson.pruning) setPruning(vJson.pruning);
        if (vJson.graduation) setGraduation(vJson.graduation);
        if (vJson.calibration) setCalibration(vJson.calibration);
      }
    } catch (e) {
      console.error('ModelHealth+Drift fetch error:', e);
    }
    setLoading(false);
  }, [asset]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  if (loading) return (
    <div className="flex items-center justify-center h-48" data-testid="model-health-loading">
      <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#94a3b8' }} />
    </div>
  );

  const horizons = health?.horizons || {};
  const worstDrift = [drift7D, drift30D].reduce((w, d) => {
    if (!d) return w;
    return (d.driftScore || 0) > (w?.driftScore || 0) ? d : w;
  }, null);
  const overallStatus = worstDrift?.status || 'OK';
  const sc = STATUS_COLORS[overallStatus];

  return (
    <div data-testid="model-health-panel" style={{ background: '#fff', borderRadius: 12 }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3" >
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4" style={{ color: '#3b82f6' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>Model Health & Drift</span>
        </div>
        <span data-testid="drift-overall-badge" className="inline-flex items-center gap-1 text-[11px] font-semibold"
          style={{ color: sc.text }}>
          {overallStatus === 'OK' ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
          {STATUS_LABELS[overallStatus]}
        </span>
      </div>

      {/* Performance: Horizon cards */}
      <div className="grid grid-cols-3" >
        {['24H', '7D', '30D'].map(h => {
          const m = horizons[h];
          if (!m) return <div key={h} className="p-3 text-center" style={{ color: '#94a3b8', fontSize: 11 }}>No data</div>;
          const winColor = m.winRate >= 0.5 ? '#16a34a' : m.winRate >= 0.3 ? '#d97706' : '#dc2626';
          return (
            <div key={h} className="p-3 space-y-2" data-testid={`model-health-${h}`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: '#64748b' }}>{h}</span>
                <span className="tabular-nums text-[10px]" style={{ color: '#94a3b8' }}>n={m.n}</span>
              </div>
              <div className="flex justify-center"><RingGauge value={m.winRate} color={winColor} /></div>
              <MRow label="TP/FP/Weak" value={`${m.tp}/${m.fp}/${m.weak}`} />
              <MRow label="Avg Error" value={m.avgErrPct > 0 ? `${m.avgErrPct.toFixed(1)}%` : '-'} />
            </div>
          );
        })}
      </div>

      {/* Drift Section */}
      <div >
        <button
          data-testid="drift-section-toggle"
          onClick={() => setDriftExpanded(e => !e)}
          className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-gray-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Shield className="w-3.5 h-3.5" style={{ color: '#6366f1' }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: '#0f172a' }}>Drift & ML Weight</span>
          </div>
          {driftExpanded
            ? <ChevronUp className="w-3.5 h-3.5" style={{ color: '#94a3b8' }} />
            : <ChevronDown className="w-3.5 h-3.5" style={{ color: '#94a3b8' }} />
          }
        </button>

        {/* Always-visible: compact drift summary */}
        {!driftExpanded && (drift7D || drift30D) && (
          <div className="px-4 pb-3 grid grid-cols-2 gap-3">
            {[{ h: '7D', d: drift7D }, { h: '30D', d: drift30D }].map(({ h, d }) => d && (
              <DriftCompact key={h} horizon={h} data={d} />
            ))}
          </div>
        )}

        {/* Expanded: full drift details + graduation + history chart + shadow verdict */}
        {driftExpanded && (
          <div className="px-4 pb-4 space-y-4" data-testid="drift-section-expanded" style={{ animation: 'fadeIn 0.3s ease' }}>
            {/* Graduation stages */}
            {graduation && (
              <GraduationBlock data={graduation} />
            )}
            {[{ h: '7D', d: drift7D }, { h: '30D', d: drift30D }].map(({ h, d }) => d && (
              <DriftDetail key={h} horizon={h} data={d} history={driftHistory[h] || []} />
            ))}
            {/* Shadow Verdict */}
            {shadowVerdict && (
              <ShadowVerdictBlock data={shadowVerdict} />
            )}
            {/* Calibration Gate */}
            {calibration && Object.keys(calibration).length > 0 && (
              <CalibrationBlock data={calibration} />
            )}
            {/* Stable Features (Pruning) */}
            {pruning && (
              <StableFeaturesBlock data={pruning} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DriftCompact({ horizon, data }) {
  const sc = STATUS_COLORS[data.status || 'OK'];
  return (
    <div data-testid={`drift-compact-${horizon}`} className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold" style={{ color: '#64748b' }}>{horizon}</span>
        <span className="text-[10px] font-semibold"
          style={{ color: sc.text }}>{data.status}</span>
      </div>
      <DriftBar value={data.driftScore} status={data.status} />
      <div className="flex justify-between">
        <span className="text-[10px]" style={{ color: '#94a3b8' }}>Drift {(data.driftScore * 100).toFixed(0)}%</span>
        <span className="text-[10px] font-medium tabular-nums" style={{ color: '#0f172a' }}>
          ML Weight {(data.mlWeight * 100).toFixed(0)}%
        </span>
      </div>
    </div>
  );
}

function DriftDetail({ horizon, data, history = [] }) {
  const sc = STATUS_COLORS[data.status || 'OK'];
  const comp = data.components || {};
  const drivers = data.drivers || [];
  const perf = data.performance || {};
  const calib = data.calibration || {};

  return (
    <div data-testid={`drift-detail-${horizon}`}
      className="rounded-lg p-3 space-y-3"
      style={{ background: '#f8fafc' }}>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[12px] font-bold" style={{ color: '#0f172a' }}>{horizon} Drift</span>
          {data.regime && (
            <span className="text-[9px]" style={{ color: '#64748b' }}>
              {data.regime}
            </span>
          )}
          {data.regimeAdjusted && (
            <span className="text-[8px]" style={{ color: '#059669' }}>
              regime-adj
            </span>
          )}
        </div>
        <span className="text-[10px] font-semibold"
          style={{ color: sc.text }}>
          {data.status}
        </span>
      </div>

      {/* Score + Weight */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] mb-1" style={{ color: '#64748b' }}>Drift Score</div>
          <DriftBar value={data.driftScore} status={data.status} />
          <div className="text-[11px] font-bold tabular-nums mt-1" style={{ color: sc.text }}>
            {(data.driftScore * 100).toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-[10px] mb-1" style={{ color: '#64748b' }}>ML Weight</div>
          <DriftBar value={data.mlWeight} status="OK" />
          <div className="text-[11px] font-bold tabular-nums mt-1" style={{ color: '#0f172a' }}>
            {(data.mlWeight * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Mini History Chart */}
      {history.length > 1 && (
        <DriftMiniChart data={history} horizon={horizon} />
      )}

      {/* Components */}
      <div className="space-y-1">
        <div className="text-[10px] font-semibold mb-1" style={{ color: '#64748b' }}>Components</div>
        <ComponentRow label="PSI (features)" value={comp.psi} />
        <ComponentRow label="DirHit drop" value={comp.dirHitDrop} />
        <ComponentRow label="MAE growth" value={comp.maeGrowth} />
        <ComponentRow label="Flip spike" value={comp.flipSpike} />
      </div>

      {/* Drivers */}
      {drivers.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold mb-1" style={{ color: '#64748b' }}>Top Drivers</div>
          {drivers.map((dr, i) => (
            <div key={i} className="flex items-center justify-between text-[10px] py-0.5">
              <span style={{ color: '#475569' }}>{dr.name}</span>
              <span className="tabular-nums font-medium" style={{ color: '#dc2626' }}>
                +{(dr.contribution * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Performance comparison */}
      {perf.baseline && perf.production && (
        <div>
          <div className="text-[10px] font-semibold mb-1" style={{ color: '#64748b' }}>Performance (Rule)</div>
          <div className="grid grid-cols-3 gap-1 text-[10px]">
            <div></div>
            <div className="text-center font-medium" style={{ color: '#94a3b8' }}>Base</div>
            <div className="text-center font-medium" style={{ color: '#94a3b8' }}>Prod</div>
            <PerfRow label="MAE" base={perf.baseline.mae} prod={perf.production.mae} fmt={v => (v*100).toFixed(2)+'%'} lower />
            <PerfRow label="DirHit" base={perf.baseline.dir_hit} prod={perf.production.dir_hit} fmt={v => (v*100).toFixed(1)+'%'} />
            <PerfRow label="Flip" base={perf.baseline.flip_rate} prod={perf.production.flip_rate} fmt={v => (v*100).toFixed(1)+'%'} lower />
          </div>
        </div>
      )}

      {/* Calibration */}
      {calib.n > 0 && (
        <div className="flex items-center justify-between">
          <span className="text-[10px]" style={{ color: '#64748b' }}>Calibration ECE</span>
          <span className="text-[10px] font-medium tabular-nums" style={{
            color: calib.status === 'DRIFT' ? '#dc2626' : calib.status === 'WATCH' ? '#d97706' : '#16a34a'
          }}>
            {(calib.ece * 100).toFixed(1)}% ({calib.status})
          </span>
        </div>
      )}
    </div>
  );
}

function DriftMiniChart({ data, horizon }) {
  const W = 260;
  const H = 48;
  const PAD = 2;

  if (data.length < 2) return null;

  const maxDrift = Math.max(0.01, ...data.map(d => d.driftScore));
  const points = data.map((d, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2);
    const y = H - PAD - ((d.driftScore / maxDrift) * (H - PAD * 2));
    return { x, y, d };
  });
  const weightPoints = data.map((d, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2);
    const y = H - PAD - (d.mlWeight * (H - PAD * 2));
    return { x, y };
  });

  const driftPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const weightPath = weightPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  return (
    <div data-testid={`drift-chart-${horizon}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] font-semibold" style={{ color: '#64748b' }}>History ({data.length}d)</span>
        <div className="flex items-center gap-2 text-[9px]">
          <span className="flex items-center gap-1"><span className="w-2 h-0.5 rounded" style={{ background: '#ef4444', display: 'inline-block' }} />Drift</span>
          <span className="flex items-center gap-1"><span className="w-2 h-0.5 rounded" style={{ background: '#3b82f6', display: 'inline-block' }} />Weight</span>
        </div>
      </div>
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} style={{ borderRadius: 4, background: '#fff' }}>
        {/* Grid */}
        <line x1={PAD} y1={H/2} x2={W-PAD} y2={H/2} stroke="#f1f5f9" strokeWidth={0.5} />
        {/* Drift line */}
        <path d={driftPath} fill="none" stroke="#ef4444" strokeWidth={1.5} strokeLinecap="round" opacity={0.8} />
        {/* Weight line */}
        <path d={weightPath} fill="none" stroke="#3b82f6" strokeWidth={1.5} strokeLinecap="round" opacity={0.6} strokeDasharray="3 2" />
      </svg>
    </div>
  );
}

const VERDICT_COLORS = {
  SHADOW_OK: { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0', label: 'GO' },
  SHADOW_WARN: { bg: '#fffbeb', text: '#d97706', border: '#fde68a', label: 'WARN' },
  SHADOW_FAIL: { bg: '#fef2f2', text: '#dc2626', border: '#fecaca', label: 'FAIL' },
  INSUFFICIENT_DATA: { bg: '#f1f5f9', text: '#64748b', border: '#e2e8f0', label: 'N/A' },
};

function ShadowVerdictBlock({ data }) {
  if (!data) return null;

  return (
    <div data-testid="shadow-verdict-block" className="rounded-lg p-3 space-y-2"
      style={{ background: '#faf5ff' }}>
      <div className="text-[11px] font-bold" style={{ color: '#6d28d9' }}>Shadow Eval Verdicts</div>
      <div className="grid grid-cols-2 gap-2">
        {['7D', '30D'].map(h => {
          const hData = data[h];
          if (!hData) return null;
          const r30 = hData.rolling_30d || {};
          const vc = VERDICT_COLORS[r30.verdict] || VERDICT_COLORS.INSUFFICIENT_DATA;
          return (
            <div key={h} data-testid={`verdict-${h}`} className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold" style={{ color: '#64748b' }}>{h}</span>
                <span className="text-[9px] font-bold"
                  style={{ color: vc.text }}>
                  {vc.label}
                </span>
              </div>
              {r30.metrics && (
                <div className="space-y-0.5 text-[9px]">
                  <div className="flex justify-between" style={{ color: '#475569' }}>
                    <span>MAE imp</span>
                    <span className="tabular-nums font-medium" style={{ color: r30.metrics.mae_improvement_pct > 0 ? '#16a34a' : '#dc2626' }}>
                      {r30.metrics.mae_improvement_pct > 0 ? '+' : ''}{r30.metrics.mae_improvement_pct?.toFixed(1)}%
                    </span>
                  </div>
                  <div className="flex justify-between" style={{ color: '#475569' }}>
                    <span>Dir delta</span>
                    <span className="tabular-nums font-medium" style={{ color: r30.metrics.dir_delta >= 0 ? '#16a34a' : '#dc2626' }}>
                      {r30.metrics.dir_delta >= 0 ? '+' : ''}{r30.metrics.dir_delta?.toFixed(1)}pp
                    </span>
                  </div>
                </div>
              )}
              {r30.n < 3 && <div className="text-[9px]" style={{ color: '#94a3b8' }}>n={r30.n} (need 3+)</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ComponentRow({ label, value }) {
  const pct = Math.min(100, (value || 0) * 100);
  const color = pct >= 50 ? '#dc2626' : pct >= 25 ? '#d97706' : '#16a34a';
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] w-20 shrink-0" style={{ color: '#64748b' }}>{label}</span>
      <div className="flex-1 h-1.5 rounded-full" style={{ background: '#e2e8f0' }}>
        <div className="h-full rounded-full" style={{
          width: `${pct}%`, background: color,
          transition: 'width 0.6s ease', minWidth: pct > 0 ? 2 : 0,
        }} />
      </div>
      <span className="text-[10px] tabular-nums w-8 text-right font-medium" style={{ color }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

function PerfRow({ label, base, prod, fmt, lower }) {
  const better = lower ? prod <= base : prod >= base;
  return (
    <>
      <div style={{ color: '#475569' }}>{label}</div>
      <div className="text-center tabular-nums" style={{ color: '#94a3b8' }}>{fmt(base)}</div>
      <div className="text-center tabular-nums font-medium" style={{ color: better ? '#16a34a' : '#dc2626' }}>
        {fmt(prod)}
      </div>
    </>
  );
}

function MRow({ label, value, valueColor = '#0f172a' }) {
  return (
    <div className="flex items-center justify-between">
      <span style={{ fontSize: 10, color: '#64748b' }}>{label}</span>
      <span className="tabular-nums text-[11px] font-medium" style={{ color: valueColor }}>{value}</span>
    </div>
  );
}


const CALIB_COLORS = {
  OK: { bg: '#f0fdf4', text: '#16a34a', border: '#bbf7d0' },
  WATCH: { bg: '#fffbeb', text: '#d97706', border: '#fde68a' },
  DRIFT: { bg: '#fef2f2', text: '#dc2626', border: '#fecaca' },
};

function CalibrationBlock({ data }) {
  if (!data) return null;
  return (
    <div data-testid="calibration-block" className="rounded-lg p-3 space-y-2"
      style={{ background: '#fdf4ff' }}>
      <div className="text-[11px] font-bold" style={{ color: '#7e22ce' }}>Calibration Gate</div>
      <div className="grid grid-cols-2 gap-2">
        {['7D', '30D'].map(h => {
          const hd = data[h];
          if (!hd) return null;
          const cc = CALIB_COLORS[hd.status] || CALIB_COLORS.OK;
          const ece = hd.ece || 0;
          const brier = hd.brier || 0;
          const penalty = hd.ecePenalty != null ? hd.ecePenalty : (ece > 0 ? Math.exp(-3.0 * ece) : 1.0);
          return (
            <div key={h} data-testid={`calibration-${h}`} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold" style={{ color: '#64748b' }}>{h}</span>
                <span className="text-[9px] font-bold"
                  style={{ color: cc.text }}>
                  {hd.status}
                </span>
              </div>
              <div className="space-y-0.5 text-[9px]">
                <div className="flex justify-between" style={{ color: '#475569' }}>
                  <span>ECE</span>
                  <span className="tabular-nums font-medium" style={{ color: cc.text }}>
                    {(ece * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between" style={{ color: '#475569' }}>
                  <span>Brier</span>
                  <span className="tabular-nums font-medium" style={{ color: '#475569' }}>
                    {brier.toFixed(4)}
                  </span>
                </div>
                <div className="flex justify-between" style={{ color: '#475569' }}>
                  <span>Weight penalty</span>
                  <span className="tabular-nums font-medium" style={{ color: penalty < 0.9 ? '#dc2626' : '#16a34a' }}>
                    x{penalty.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}



function StableFeaturesBlock({ data }) {
  if (!data) return null;
  return (
    <div data-testid="stable-features-block" className="rounded-lg p-3 space-y-2"
      style={{ background: '#f0f9ff' }}>
      <div className="text-[11px] font-bold" style={{ color: '#1d4ed8' }}>Stable Features</div>
      <div className="space-y-2">
        {['7D', '30D'].map(h => {
          const hd = data[h];
          if (!hd) return null;
          return (
            <div key={h} data-testid={`stable-features-${h}`}>
              <div className="flex items-center gap-1 mb-1">
                <span className="text-[10px] font-semibold" style={{ color: '#64748b' }}>{h}</span>
                <span className="text-[9px]" style={{ color: '#94a3b8' }}>
                  {hd.selected.length} active / {hd.prunedCount} pruned
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                {hd.selected.map(f => (
                  <span key={f} className="text-[9px] font-medium"
                    style={{ color: '#1e40af' }}>
                    {f}
                  </span>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}


const STAGE_LABELS = {
  SHADOW: 'Shadow',
  LIVE_LITE: 'Live 50%',
  LIVE_MED: 'Live 75%',
  LIVE_FULL: 'Live 100%',
};

const STAGE_COLORS = {
  SHADOW: { bg: '#faf5ff', text: '#7c3aed', fill: '#a78bfa' },
  LIVE_LITE: { bg: '#ecfdf5', text: '#059669', fill: '#34d399' },
  LIVE_MED: { bg: '#ecfdf5', text: '#059669', fill: '#10b981' },
  LIVE_FULL: { bg: '#f0fdf4', text: '#16a34a', fill: '#22c55e' },
};

function GraduationBlock({ data }) {
  if (!data) return null;
  const stages = ['SHADOW', 'LIVE_LITE', 'LIVE_MED', 'LIVE_FULL'];

  return (
    <div data-testid="graduation-block" className="rounded-lg p-3 space-y-2.5"
      style={{ background: '#fefce8' }}>
      <div className="text-[11px] font-bold" style={{ color: '#a16207' }}>Graduation Plan</div>
      <div className="grid grid-cols-2 gap-2">
        {['7D', '30D'].map(h => {
          const hd = data[h];
          if (!hd) return null;
          const sc = STAGE_COLORS[hd.stage] || STAGE_COLORS.SHADOW;
          const stageIdx = stages.indexOf(hd.stage);
          return (
            <div key={h} data-testid={`graduation-${h}`} className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-semibold" style={{ color: '#64748b' }}>{h}</span>
                <span className="text-[9px] font-bold"
                  style={{ color: sc.text }}>
                  {STAGE_LABELS[hd.stage]}
                </span>
              </div>
              {/* Stage progress bar */}
              <div className="flex gap-0.5">
                {stages.map((s, i) => (
                  <div key={s} className="flex-1 h-1.5 rounded-full"
                    style={{
                      background: i <= stageIdx ? sc.fill : '#e2e8f0',
                      transition: 'background 0.3s ease',
                    }} />
                ))}
              </div>
              <div className="flex justify-between text-[9px]">
                <span style={{ color: '#94a3b8' }}>
                  alpha {(hd.mlAlpha * 100).toFixed(0)}%
                </span>
                <span className="tabular-nums font-medium" style={{ color: '#0f172a' }}>
                  eff {(hd.effectiveAlpha * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
