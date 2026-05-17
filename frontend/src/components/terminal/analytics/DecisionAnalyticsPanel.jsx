/**
 * Decision Analytics Panel — Sprint 5
 * 
 * READ ONLY. Answers 4 questions:
 * 1. Is system profitable? → Win Rate + Avg PnL
 * 2. Does operator help? → Operator Override %
 * 3. Does R2 matter? → R2 Active %
 * 4. Where is the problem? → Wins vs Losses
 * 
 * Design: Trading Terminal style (white, Gilroy).
 * No graphs. No filters. Only answers.
 */

function MetricRow({ label, value, color, suffix = '' }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-neutral-100 last:border-0">
      <span className="text-[12px] text-neutral-500">{label}</span>
      <span className="text-[14px] font-bold" style={{ color: color || '#0f172a' }}>
        {value}{suffix}
      </span>
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-2 mt-4 first:mt-0">
      {children}
    </div>
  );
}

export default function DecisionAnalyticsPanel({ data, loading }) {
  if (loading) {
    return (
      <div className="bg-white border border-neutral-200 rounded-lg p-4 col-span-full" data-testid="decision-analytics-panel">
        <div className="text-[12px] text-neutral-400">Loading decision analytics...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white border border-neutral-200 rounded-lg p-4 col-span-full" data-testid="decision-analytics-panel">
        <div className="text-[12px] text-neutral-400">No analytics data</div>
      </div>
    );
  }

  const winColor = data.win_rate_pct >= 50 ? '#16a34a' : '#dc2626';
  const pnlColor = data.avg_pnl_pct >= 0 ? '#16a34a' : '#dc2626';

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4 col-span-full" data-testid="decision-analytics-panel" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <div className="text-[14px] font-bold text-neutral-900 mb-1">DECISION PERFORMANCE</div>
      <div className="text-[11px] text-neutral-400 mb-3">Decision-centric analytics · read only</div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Column 1: Performance */}
        <div>
          <SectionTitle>Performance</SectionTitle>
          <MetricRow label="Win Rate" value={data.win_rate_pct} suffix="%" color={winColor} />
          <MetricRow label="Avg PnL" value={data.avg_pnl_pct > 0 ? `+${data.avg_pnl_pct}` : data.avg_pnl_pct} suffix="%" color={pnlColor} />
          <MetricRow label="Total PnL" value={`$${data.total_pnl_usd}`} color={data.total_pnl_usd >= 0 ? '#16a34a' : '#dc2626'} />
          <MetricRow label="Avg Duration" value={data.avg_duration_sec > 0 ? `${Math.round(data.avg_duration_sec / 60)}m` : '—'} />
        </div>

        {/* Column 2: Decisions */}
        <div>
          <SectionTitle>Decisions</SectionTitle>
          <MetricRow label="Total" value={data.total_decisions} />
          <MetricRow label="Wins" value={data.wins} color="#16a34a" />
          <MetricRow label="Losses" value={data.losses} color="#dc2626" />
          <MetricRow label="Breakeven" value={data.breakeven} color="#64748b" />
          <MetricRow label="Pending" value={data.pending} color="#ca8a04" />
          <MetricRow label="Executed" value={data.executed} color="#059669" />
        </div>

        {/* Column 3: System */}
        <div>
          <SectionTitle>System</SectionTitle>
          <MetricRow label="Operator Override" value={data.operator_override_pct} suffix="%" />
          <MetricRow label="R2 Active" value={data.r2_active_pct} suffix="%" />
          <MetricRow label="Source: TA Engine" value={data.source_ta} />
          <MetricRow label="Source: Manual" value={data.source_manual} />
          <MetricRow label="Total Traces" value={data.total_traces} />
        </div>
      </div>
    </div>
  );
}
