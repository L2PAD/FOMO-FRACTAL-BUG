export default function ExecutionStatsBar({ events = [], orders = [], fills = [] }) {
  const queued = events.filter(e => String(e.type || e.event_type).toUpperCase().includes("QUEUED")).length;
  const filled = events.filter(e => String(e.type || e.event_type).toUpperCase().includes("FILLED")).length;
  const blocked = events.filter(e => String(e.type || e.event_type).toUpperCase().includes("BLOCKED")).length;

  const StatItem = ({ label, value, color = "text-white" }) => (
    <div className="bg-gray-900/60 border border-gray-800 rounded-lg px-4 py-3" data-testid={`stat-${label.toLowerCase()}`}>
      <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold ${color} mt-1`}>{value}</div>
    </div>
  );

  return (
    <div className="grid grid-cols-5 gap-4" data-testid="execution-stats-bar">
      <StatItem label="Events" value={events.length} />
      <StatItem label="Orders" value={orders.length} color="text-blue-400" />
      <StatItem label="Fills" value={fills.length} color="text-green-400" />
      <StatItem label="Queued" value={queued} color="text-yellow-400" />
      <StatItem label="Blocked" value={blocked} color="text-red-400" />
    </div>
  );
}
