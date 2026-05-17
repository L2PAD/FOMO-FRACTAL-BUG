import { useStrategyLiveSignals } from "@/hooks/strategy/useStrategyLiveSignals";
import { WsConnectionBadge } from "../WsConnectionBadge";

export default function LiveSignalStream() {
  const { data, error, isConnected } = useStrategyLiveSignals();

  if (error) {
    return (
      <div className="bg-neutral-900 rounded-xl p-6 border border-red-600/20">
        <div className="text-red-500 text-sm">Signals error: {error}</div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-neutral-900 rounded-xl p-6 text-center text-gray-400 border border-neutral-800">
        <div className="text-base font-medium mb-2">No valid setups detected</div>
        <div className="text-xs">System is monitoring live market structure</div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-medium text-gray-300">
          Live Signals ({data.length})
        </div>
        <WsConnectionBadge isConnected={isConnected} />
      </div>
      {data.map((s, i) => (
        <SignalCard key={i} s={s} />
      ))}
    </div>
  );
}

function SignalCard({ s }) {
  const sideColor = s.direction === "LONG" ? "text-green-400" : "text-red-400";

  return (
    <div
      className="bg-neutral-900 rounded-xl p-4 border border-neutral-800 hover:border-neutral-700 transition-colors"
      data-testid={`signal-card-${s.symbol}`}
    >
      <div className="flex justify-between items-center mb-2">
        <div className="font-semibold text-gray-100">{s.symbol}</div>
        <div className={`text-sm font-medium ${sideColor}`}>{s.direction}</div>
      </div>

      <div className="text-xs text-gray-400 mb-2">
        {s.strategy} · {s.regime}
      </div>

      <div className="text-sm text-gray-300 mb-2">{s.thesis}</div>

      <div className="flex justify-between text-xs text-gray-400 mb-2">
        <span>Confidence: {(s.confidence * 100).toFixed(1)}%</span>
        <span>{s.source}</span>
      </div>

      {s.drivers && Object.keys(s.drivers).length > 0 && (
        <div className="mt-2 flex gap-2 text-xs flex-wrap">
          {Object.entries(s.drivers).map(([k, v]) => (
            <span key={k} className="bg-neutral-800 px-2 py-1 rounded border border-neutral-700">
              {k}: {typeof v === "number" ? v.toFixed(1) : v}
            </span>
          ))}
        </div>
      )}

      <StatusBadge status={s.status} reason={s.risk_reason} />
    </div>
  );
}

function StatusBadge({ status, reason }) {
  const color =
    status === "APPROVED"
      ? "bg-green-600/20 text-green-400 border-green-600/40"
      : status === "REJECTED"
      ? "bg-red-600/20 text-red-400 border-red-600/40"
      : "bg-yellow-600/20 text-yellow-400 border-yellow-600/40";

  return (
    <div className={`mt-3 inline-block text-xs px-2 py-1 rounded border ${color}`}>
      {status}
      {reason && ` · ${reason}`}
    </div>
  );
}
