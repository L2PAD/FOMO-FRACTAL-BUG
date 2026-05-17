function formatTs(ts) {
  if (!ts) return "-";
  const date = new Date(ts);
  return date.toLocaleTimeString();
}

export default function FillsTable({ fills = [] }) {
  return (
    <div className="bg-gray-900/60 border border-gray-800 rounded-lg p-4" data-testid="fills-table">
      <div className="text-white font-semibold mb-3">Fills</div>

      {!fills.length ? (
        <div className="text-gray-500 text-sm text-center py-6">No fills</div>
      ) : (
        <div className="space-y-2 max-h-[300px] overflow-y-auto custom-scrollbar">
          {fills.map((f, i) => (
            <div 
              key={i} 
              className="grid grid-cols-5 gap-3 text-sm border-b border-gray-800/50 pb-2 hover:bg-gray-800/30 px-2 py-1 rounded transition-colors"
              data-testid={`fill-${i}`}
            >
              <div className="text-white font-medium">{f.symbol}</div>
              <div className={f.side === "BUY" ? "text-green-400" : "text-red-400"}>
                {f.side}
              </div>
              <div className="text-gray-300">${f.price}</div>
              <div className="text-gray-300">{f.qty || f.quantity}</div>
              <div className="text-gray-400 text-xs">{formatTs(f.timestamp || f.created_at)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
