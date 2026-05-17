/**
 * Channel Chart (Full for detail page)
 */
import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';

function fmtDate(d) {
  try {
    return new Date(d).toLocaleDateString();
  } catch {
    return '';
  }
}

function num(v) {
  if (v == null) return '—';
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString() : '—';
}

export function ChannelChart({ rows }) {
  const data = (rows || []).map((r) => ({
    date: r.date,
    utility: r.utility == null ? null : Number(r.utility),
    reach: r.reach == null ? null : Number(r.reach),
    growth7: r.growth7 == null ? null : Number(r.growth7) * 100,
    fraud: r.fraud == null ? null : Number(r.fraud) * 100,
  }));

  if (data.length < 2) {
    return <div className="h-64 flex items-center justify-center text-gray-400">No timeline data</div>;
  }

  return (
    <div className="w-full h-72">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#e5e7eb" strokeDasharray="4 4" />
          <XAxis
            dataKey="date"
            tickFormatter={fmtDate}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={{ stroke: '#e5e7eb' }}
            minTickGap={20}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={{ stroke: '#e5e7eb' }}
            width={40}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={{ stroke: '#e5e7eb' }}
            width={46}
          />

          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: '1px solid #e5e7eb',
              boxShadow: '0 18px 40px rgba(0,0,0,0.12)',
              fontSize: 12,
            }}
            labelFormatter={(l) => `Date: ${fmtDate(l)}`}
            formatter={(v, name) => {
              if (name === 'utility') return [num(v), 'Utility'];
              if (name === 'reach') return [num(v), 'Avg Reach'];
              if (name === 'growth7') return [`${Number(v).toFixed(1)}%`, 'Growth 7D'];
              if (name === 'fraud') return [`${Number(v).toFixed(0)}%`, 'Fraud'];
              return [v, name];
            }}
          />

          <Line yAxisId="left" type="monotone" dataKey="utility" stroke="#111827" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line yAxisId="left" type="monotone" dataKey="reach" stroke="#9ca3af" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line yAxisId="right" type="monotone" dataKey="growth7" stroke="#374151" strokeWidth={1.8} dot={false} isAnimationActive={false} />
          <Line yAxisId="right" type="monotone" dataKey="fraud" stroke="#6b7280" strokeWidth={1.2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
