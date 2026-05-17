/**
 * Score Evolution Chart
 * Multi-line chart with toggles and delta badges
 */
import { useMemo, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

function clamp(n, a, b) {
  return Math.max(a, Math.min(b, n));
}

function findDelta(data, daysBack) {
  if (!data.length) return { delta: 0, from: null, to: null };
  const last = data[data.length - 1];
  const idx = Math.max(0, data.length - 1 - daysBack);
  const prev = data[idx];
  const delta = (last?.intel ?? 0) - (prev?.intel ?? 0);
  return { delta, from: prev, to: last };
}

function fmtDelta(x) {
  const v = Math.round(x * 10) / 10;
  return (v > 0 ? '+' : '') + v.toFixed(1);
}

function Badge({ label, value }) {
  const up = value >= 0;
  return (
    <div className="px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 text-sm flex items-center gap-2">
      <span className="text-gray-600">{label}</span>
      <span className={up ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold'}>
        {fmtDelta(value)}
      </span>
    </div>
  );
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload.reduce((acc, item) => {
    acc[item.dataKey] = item.value;
    acc.day = item.payload.day;
    return acc;
  }, {});

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm px-4 py-3 text-sm">
      <div className="font-medium text-gray-800 mb-2">{p.day}</div>
      <div className="space-y-1 text-gray-700">
        {'intel' in p && <div>Intel: <span className="font-semibold text-blue-600">{Number(p.intel).toFixed(1)}</span></div>}
        {'alpha' in p && <div>Alpha: <span className="font-semibold text-emerald-600">{Number(p.alpha).toFixed(1)}</span></div>}
        {'cred' in p && <div>Cred: <span className="font-semibold text-amber-600">{Number(p.cred).toFixed(1)}</span></div>}
        {'net' in p && <div>Net: <span className="font-semibold text-violet-600">{Number(p.net).toFixed(1)}</span></div>}
      </div>
    </div>
  );
}

export default function ScoreChart({ data = [] }) {
  const [show, setShow] = useState({
    intel: true,
    alpha: true,
    cred: true,
    net: true
  });

  const formatted = useMemo(() => {
    return (data || []).map((d) => ({
      day: d.day,
      intel: clamp(Number(d.scores?.intelScore ?? 0), 0, 100),
      alpha: clamp(Number(d.scores?.alphaScore ?? 0), 0, 100),
      cred: clamp(Number(d.scores?.credibilityScore ?? 0), 0, 100),
      net: clamp(Number(d.scores?.networkAlphaScore ?? 0), 0, 100),
    }));
  }, [data]);

  const d7 = useMemo(() => findDelta(formatted, 7), [formatted]);
  const d30 = useMemo(() => findDelta(formatted, 30), [formatted]);

  const Toggle = ({ k, label, color }) => (
    <button
      onClick={() => setShow((s) => ({ ...s, [k]: !s[k] }))}
      className={`px-3 py-1.5 rounded-lg border text-sm transition ${
        show[k] ? 'bg-white border-gray-200' : 'bg-gray-50 border-gray-200 text-gray-400'
      }`}
      title={`Toggle ${label}`}
    >
      <span className="inline-flex items-center gap-2">
        <span className="w-2 h-2 rounded-full" style={{ background: color }} />
        {label}
      </span>
    </button>
  );

  if (!data.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-6 text-center text-gray-500">
        No temporal data available. Run snapshot first.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="score-chart">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Score Evolution</h2>
          <div className="text-sm text-gray-500 mt-1">Last 90 days</div>
        </div>
        <div className="flex items-center gap-2">
          <Badge label="Δ7d" value={d7.delta} />
          <Badge label="Δ30d" value={d30.delta} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <Toggle k="intel" label="Intel" color="#2563EB" />
        <Toggle k="alpha" label="Alpha" color="#10B981" />
        <Toggle k="cred" label="Cred" color="#F59E0B" />
        <Toggle k="net" label="NetAlpha" color="#7C3AED" />
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={formatted}>
          <XAxis dataKey="day" hide />
          <YAxis domain={[0, 100]} width={36} />
          <Tooltip content={<CustomTooltip />} />
          {show.intel && <Line type="monotone" dataKey="intel" stroke="#2563EB" strokeWidth={2} dot={false} />}
          {show.alpha && <Line type="monotone" dataKey="alpha" stroke="#10B981" strokeWidth={1.7} dot={false} />}
          {show.cred && <Line type="monotone" dataKey="cred" stroke="#F59E0B" strokeWidth={1.7} dot={false} />}
          {show.net && <Line type="monotone" dataKey="net" stroke="#7C3AED" strokeWidth={1.7} dot={false} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
