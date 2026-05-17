/**
 * CAS Historical Chart
 * 
 * Full-page chart with:
 * - 24h / 7d / 30d toggle
 * - EMA overlay (6h line)
 * - Peak coordination event highlights
 * - Tooltip with Z-score breakdown
 * - Responsive SVG rendering
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Activity, TrendingUp, AlertTriangle, RefreshCw } from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

const RANGES = [
  { key: '24h', label: '24h', hours: 24 },
  { key: '7d', label: '7d', hours: 168 },
  { key: '30d', label: '30d', hours: 720 },
];

export default function CASHistoryChart() {
  const [range, setRange] = useState('24h');
  const [casData, setCasData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState(null);
  const svgRef = useRef(null);

  const fetchCAS = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/connections/overview/cas`);
      const data = await res.json();
      if (data.ok) setCasData(data);
    } catch (err) {
      console.error('CAS fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchCAS(); }, [fetchCAS]);

  if (loading) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 p-8 flex items-center justify-center" data-testid="cas-history-loading">
        <RefreshCw className="w-5 h-5 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (!casData) return null;

  const history = casData.history || [];
  const rangeConfig = RANGES.find(r => r.key === range);
  const cutoffTs = Date.now() / 1000 - (rangeConfig?.hours || 24) * 3600;
  const filtered = history.filter(h => h.ts >= cutoffTs);

  // Generate display points (pad if needed)
  const points = filtered.length > 0 ? filtered : [{ ts: Date.now() / 1000, value: casData.ema6h || casData.current, raw: casData.current }];

  const W = 800, H = 220, PAD_X = 48, PAD_Y = 24, PAD_B = 32;
  const chartW = W - PAD_X * 2;
  const chartH = H - PAD_Y - PAD_B;

  const values = points.map(p => p.value);
  const rawValues = points.map(p => p.raw ?? p.value);
  const allVals = [...values, ...rawValues];
  const minV = Math.max(Math.min(...allVals) - 5, 0);
  const maxV = Math.min(Math.max(...allVals) + 5, 100);
  const rangeV = maxV - minV || 1;

  const minTs = points[0]?.ts || 0;
  const maxTs = points[points.length - 1]?.ts || 1;
  const rangeTs = maxTs - minTs || 1;

  const xOf = (ts) => PAD_X + ((ts - minTs) / rangeTs) * chartW;
  const yOf = (v) => PAD_Y + (1 - (v - minV) / rangeV) * chartH;

  // EMA line points
  const emaPoints = points.map(p => `${xOf(p.ts)},${yOf(p.value)}`).join(' ');
  // Raw CAS line points
  const rawPoints = points.map(p => `${xOf(p.ts)},${yOf(p.raw ?? p.value)}`).join(' ');
  // Area fill under EMA
  const areaPoints = `${xOf(points[0]?.ts || 0)},${H - PAD_B} ${emaPoints} ${xOf(points[points.length - 1]?.ts || 0)},${H - PAD_B}`;

  // Peak events (CAS > 75)
  const peaks = points.filter(p => (p.value || 0) >= 75);

  // Y-axis grid lines
  const yGridSteps = 5;
  const yGridLines = Array.from({ length: yGridSteps + 1 }, (_, i) => {
    const v = minV + (i / yGridSteps) * rangeV;
    return { y: yOf(v), label: Math.round(v) };
  });

  // Color based on current value
  const currentVal = casData.ema6h || casData.current;
  const lineColor = currentVal >= 75 ? '#ef4444' : currentVal >= 60 ? '#f97316' : currentVal >= 30 ? '#eab308' : '#22c55e';
  const fillColor = currentVal >= 75 ? 'rgba(239,68,68,0.08)' : currentVal >= 60 ? 'rgba(249,115,22,0.08)' : currentVal >= 30 ? 'rgba(234,179,8,0.08)' : 'rgba(34,197,94,0.08)';

  const handleMouseMove = (e) => {
    if (!svgRef.current || points.length < 2) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const scaledX = (mouseX / rect.width) * W;
    const ts = minTs + ((scaledX - PAD_X) / chartW) * rangeTs;

    let closest = points[0], minDist = Infinity;
    for (const p of points) {
      const dist = Math.abs(p.ts - ts);
      if (dist < minDist) { minDist = dist; closest = p; }
    }

    setTooltip({
      x: xOf(closest.ts),
      y: yOf(closest.value),
      ema: closest.value,
      raw: closest.raw ?? closest.value,
      ts: closest.ts,
    });
  };

  const formatTime = (ts) => {
    const d = new Date(ts * 1000);
    if (range === '24h') return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (range === '7d') return d.toLocaleDateString([], { weekday: 'short', hour: '2-digit' });
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden" data-testid="cas-history-chart">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 flex items-center justify-between border-b border-gray-100">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
            <Activity className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900">CAS History</h3>
            <p className="text-[10px] text-gray-500">Coordinated Activity Score over time</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Current CAS badge */}
          <div className="flex items-center gap-2">
            <span className={`text-lg font-black ${currentVal >= 75 ? 'text-red-600' : currentVal >= 60 ? 'text-orange-600' : currentVal >= 30 ? 'text-amber-600' : 'text-green-600'}`}>
              {Math.round(currentVal)}
            </span>
            <span className="text-xs text-gray-400">/100</span>
            {casData.trend === 'up' && <TrendingUp className="w-3.5 h-3.5 text-red-500" />}
            {casData.trend === 'down' && <TrendingUp className="w-3.5 h-3.5 text-green-500 rotate-180" />}
            {casData.delta24h !== 0 && (
              <span className={`text-[11px] font-bold ${casData.delta24h > 0 ? 'text-red-500' : 'text-green-500'}`}>
                {casData.delta24h > 0 ? '+' : ''}{casData.delta24h}
              </span>
            )}
          </div>

          {/* Range toggle */}
          <div className="flex bg-gray-100 rounded-lg p-0.5">
            {RANGES.map(r => (
              <button
                key={r.key}
                onClick={() => setRange(r.key)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition ${
                  range === r.key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
                }`}
                data-testid={`cas-range-${r.key}`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="px-5 py-4">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          style={{ height: 220 }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setTooltip(null)}
          data-testid="cas-chart-svg"
        >
          {/* Grid lines */}
          {yGridLines.map((g, i) => (
            <g key={i}>
              <line x1={PAD_X} y1={g.y} x2={W - PAD_X} y2={g.y} stroke="#f3f4f6" strokeWidth="1" />
              <text x={PAD_X - 8} y={g.y + 4} textAnchor="end" fontSize="9" fill="#9ca3af">{g.label}</text>
            </g>
          ))}

          {/* Threshold lines */}
          <line x1={PAD_X} y1={yOf(75)} x2={W - PAD_X} y2={yOf(75)} stroke="#ef4444" strokeWidth="0.5" strokeDasharray="4 4" opacity="0.5" />
          <text x={W - PAD_X + 4} y={yOf(75) + 3} fontSize="8" fill="#ef4444">75</text>
          <line x1={PAD_X} y1={yOf(30)} x2={W - PAD_X} y2={yOf(30)} stroke="#22c55e" strokeWidth="0.5" strokeDasharray="4 4" opacity="0.5" />
          <text x={W - PAD_X + 4} y={yOf(30) + 3} fontSize="8" fill="#22c55e">30</text>

          {/* Area fill */}
          <polygon points={areaPoints} fill={fillColor} />

          {/* Raw CAS line (dashed, lighter) */}
          {points.length > 1 && (
            <polyline points={rawPoints} fill="none" stroke="#d1d5db" strokeWidth="1" strokeDasharray="3 3" />
          )}

          {/* EMA line (main) */}
          {points.length > 1 && (
            <polyline points={emaPoints} fill="none" stroke={lineColor} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          )}

          {/* Data points */}
          {points.map((p, i) => (
            <circle key={i} cx={xOf(p.ts)} cy={yOf(p.value)} r="3" fill={lineColor} stroke="white" strokeWidth="1.5" />
          ))}

          {/* Peak event markers */}
          {peaks.map((p, i) => (
            <g key={`peak-${i}`}>
              <circle cx={xOf(p.ts)} cy={yOf(p.value)} r="6" fill="none" stroke="#ef4444" strokeWidth="1.5" opacity="0.6" />
              <circle cx={xOf(p.ts)} cy={yOf(p.value)} r="10" fill="none" stroke="#ef4444" strokeWidth="0.5" opacity="0.3" />
            </g>
          ))}

          {/* X-axis labels */}
          {points.length > 1 && Array.from({ length: Math.min(points.length, 6) }, (_, i) => {
            const idx = Math.floor(i * (points.length - 1) / 5);
            const p = points[idx];
            return (
              <text key={i} x={xOf(p.ts)} y={H - 8} textAnchor="middle" fontSize="9" fill="#9ca3af">
                {formatTime(p.ts)}
              </text>
            );
          })}

          {/* Tooltip */}
          {tooltip && (
            <g>
              <line x1={tooltip.x} y1={PAD_Y} x2={tooltip.x} y2={H - PAD_B} stroke="#6b7280" strokeWidth="0.5" strokeDasharray="2 2" />
              <circle cx={tooltip.x} cy={tooltip.y} r="5" fill={lineColor} stroke="white" strokeWidth="2" />
              <rect x={tooltip.x - 44} y={tooltip.y - 38} width="88" height="32" rx="6" fill="white" stroke="#e5e7eb" />
              <text x={tooltip.x} y={tooltip.y - 24} textAnchor="middle" fontSize="10" fontWeight="bold" fill="#111827">
                EMA: {Math.round(tooltip.ema)}
              </text>
              <text x={tooltip.x} y={tooltip.y - 12} textAnchor="middle" fontSize="8" fill="#9ca3af">
                Raw: {Math.round(tooltip.raw)}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* Legend + Z-scores */}
      <div className="px-5 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-4 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 rounded" style={{ backgroundColor: lineColor }} /> EMA 6h
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 rounded bg-gray-300" style={{ borderTop: '1px dashed #d1d5db' }} /> Raw
          </span>
          {peaks.length > 0 && (
            <span className="flex items-center gap-1 text-red-500">
              <AlertTriangle className="w-3 h-3" /> {peaks.length} peak{peaks.length > 1 ? 's' : ''} (&gt;75)
            </span>
          )}
        </div>
        {casData.zScores && (
          <div className="flex items-center gap-3 text-[10px] text-gray-400">
            <span>Z: cluster={casData.zScores.cluster}</span>
            <span>velocity={casData.zScores.velocity}</span>
            <span>farm={casData.zScores.farm}</span>
            <span>bot={casData.zScores.bot}</span>
          </div>
        )}
      </div>
    </div>
  );
}
