import { useStrategySummary } from "@/hooks/strategy/useStrategySummary";

export default function StrategySummaryBar() {
  const { data, error } = useStrategySummary();

  if (error) {
    return <div className="text-red-500 text-sm">Strategy summary error: {error}</div>;
  }

  if (!data) {
    return <div className="text-gray-400 text-sm">Loading strategy summary...</div>;
  }

  const Item = ({ label, value }) => (
    <div className="bg-neutral-900 rounded-lg px-4 py-3 flex flex-col border border-neutral-800">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-lg font-semibold">{value}</span>
    </div>
  );

  return (
    <div className="grid grid-cols-5 gap-4">
      <Item label="Live Signals" value={data.live_signals} />
      <Item label="Approved" value={data.approved} />
      <Item label="Rejected" value={data.rejected} />
      <Item label="Pending" value={data.pending} />
      <Item label="Executed" value={data.executed} />
    </div>
  );
}
