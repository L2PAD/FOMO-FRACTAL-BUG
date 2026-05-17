import { LineChart, Line, ResponsiveContainer } from 'recharts';

export default function MiniSparkline({ data = [], color = "#111827" }) {
  if (!data || data.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-50 rounded">
        <span className="text-xs text-gray-400">No data</span>
      </div>
    );
  }

  // Transform data for recharts
  const chartData = data.map(point => ({
    value: point.value
  }));

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartData}>
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
