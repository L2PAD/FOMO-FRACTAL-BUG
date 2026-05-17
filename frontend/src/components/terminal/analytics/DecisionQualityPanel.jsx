/**
 * Decision Quality Panel — P2 Analytics
 * 
 * 4 blocks: Core Metrics, Confidence Calibration, Direction Analysis, Recent Losses
 * Matches existing Analytics tab style (white cards, dark text, light theme).
 */

function MetricCard({ label, value, color, testId }) {
  return (
    <div className="bg-neutral-50 border border-neutral-200 rounded-lg p-3 text-center" data-testid={testId}>
      <div className="text-[11px] text-neutral-500 mb-1">{label}</div>
      <div className="text-[18px] font-bold" style={{ color: color || '#0f172a' }}>{value}</div>
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <div className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mb-2">
      {children}
    </div>
  );
}

function CoreMetrics({ data }) {
  const wrColor = data.win_rate >= 50 ? '#16a34a' : '#dc2626';
  const pfColor = data.profit_factor >= 1.0 ? '#16a34a' : '#dc2626';

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4" data-testid="dq-core-metrics">
      <div className="text-[14px] font-bold text-neutral-900 mb-1">DECISION QUALITY</div>
      <div className="text-[11px] text-neutral-400 mb-3">Core performance metrics</div>
      <div className="grid grid-cols-5 gap-3">
        <MetricCard label="Total Trades" value={data.total_trades} testId="dq-total-trades" />
        <MetricCard label="Win Rate" value={`${data.win_rate}%`} color={wrColor} testId="dq-win-rate" />
        <MetricCard label="Avg Win" value={`$${data.avg_win}`} color="#16a34a" testId="dq-avg-win" />
        <MetricCard label="Avg Loss" value={`$${data.avg_loss}`} color="#dc2626" testId="dq-avg-loss" />
        <MetricCard label="Profit Factor" value={data.profit_factor} color={pfColor} testId="dq-profit-factor" />
      </div>
    </div>
  );
}

function ConfidenceCalibration({ data }) {
  if (!data || Object.keys(data).length === 0) return null;
  const buckets = Object.entries(data).filter(([, v]) => v.trades > 0);

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4" data-testid="dq-confidence-calibration">
      <SectionTitle>Confidence Calibration</SectionTitle>
      <table className="w-full text-[12px]">
        <thead>
          <tr className="text-neutral-400 border-b border-neutral-100">
            <th className="text-left py-1 font-medium">Bucket</th>
            <th className="text-right py-1 font-medium">Trades</th>
            <th className="text-right py-1 font-medium">Win Rate</th>
            <th className="text-right py-1 font-medium">Avg PnL</th>
          </tr>
        </thead>
        <tbody>
          {buckets.map(([bucket, v]) => (
            <tr key={bucket} className="border-b border-neutral-50">
              <td className="py-1.5 text-neutral-700 font-medium">{bucket}</td>
              <td className="py-1.5 text-right text-neutral-600">{v.trades}</td>
              <td className="py-1.5 text-right font-bold" style={{ color: v.win_rate >= 50 ? '#16a34a' : '#dc2626' }}>
                {v.win_rate}%
              </td>
              <td className="py-1.5 text-right font-bold" style={{ color: v.avg_pnl >= 0 ? '#16a34a' : '#dc2626' }}>
                ${v.avg_pnl}
              </td>
            </tr>
          ))}
          {buckets.length === 0 && (
            <tr><td colSpan={4} className="py-2 text-neutral-400 text-center">No data</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function DirectionAnalysis({ data }) {
  if (!data) return null;

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4" data-testid="dq-direction-analysis">
      <SectionTitle>Direction Analysis</SectionTitle>
      <div className="grid grid-cols-2 gap-4">
        {["LONG", "SHORT"].map((dir) => {
          const d = data[dir] || { trades: 0, win_rate: 0, avg_pnl: 0, total_pnl: 0 };
          return (
            <div key={dir} className="bg-neutral-50 border border-neutral-200 rounded-lg p-3">
              <div className="text-[12px] font-bold text-neutral-700 mb-2">{dir}</div>
              <div className="space-y-1 text-[12px]">
                <div className="flex justify-between">
                  <span className="text-neutral-500">Trades</span>
                  <span className="font-bold text-neutral-800">{d.trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Win Rate</span>
                  <span className="font-bold" style={{ color: d.win_rate >= 50 ? '#16a34a' : '#dc2626' }}>{d.win_rate}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Avg PnL</span>
                  <span className="font-bold" style={{ color: d.avg_pnl >= 0 ? '#16a34a' : '#dc2626' }}>${d.avg_pnl}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-500">Total PnL</span>
                  <span className="font-bold" style={{ color: d.total_pnl >= 0 ? '#16a34a' : '#dc2626' }}>${d.total_pnl}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecentLosses({ losses }) {
  if (!losses || losses.length === 0) return null;

  return (
    <div className="bg-white border border-neutral-200 rounded-lg p-4" data-testid="dq-recent-losses">
      <SectionTitle>Recent Losses (Last 10)</SectionTitle>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-neutral-400 border-b border-neutral-100">
              <th className="text-left py-1 font-medium">Symbol</th>
              <th className="text-left py-1 font-medium">Side</th>
              <th className="text-right py-1 font-medium">Conf</th>
              <th className="text-right py-1 font-medium">Entry</th>
              <th className="text-right py-1 font-medium">Exit</th>
              <th className="text-right py-1 font-medium">PnL</th>
              <th className="text-right py-1 font-medium">Time</th>
            </tr>
          </thead>
          <tbody>
            {losses.map((l, i) => (
              <tr key={i} className="border-b border-neutral-50">
                <td className="py-1.5 text-neutral-700 font-medium">{l.symbol}</td>
                <td className="py-1.5 text-neutral-600">{l.side}</td>
                <td className="py-1.5 text-right text-neutral-600">{l.confidence}</td>
                <td className="py-1.5 text-right text-neutral-600">${Number(l.entry_price).toLocaleString()}</td>
                <td className="py-1.5 text-right text-neutral-600">${Number(l.exit_price).toLocaleString()}</td>
                <td className="py-1.5 text-right font-bold text-red-600">${l.pnl}</td>
                <td className="py-1.5 text-right text-neutral-400 text-[11px]">
                  {l.timestamp ? new Date(l.timestamp).toLocaleTimeString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function DecisionQualityPanel({ data, loading }) {
  if (loading) {
    return (
      <div className="bg-white border border-neutral-200 rounded-lg p-4 col-span-full" data-testid="dq-panel">
        <div className="text-[12px] text-neutral-400">Loading decision quality analytics...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-white border border-neutral-200 rounded-lg p-4 col-span-full" data-testid="dq-panel">
        <div className="text-[12px] text-neutral-400">No decision quality data available</div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="dq-panel" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <CoreMetrics data={data} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ConfidenceCalibration data={data.by_confidence} />
        <DirectionAnalysis data={data.by_direction} />
      </div>
      <RecentLosses losses={data.recent_losses} />
    </div>
  );
}
