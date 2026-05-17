import { useEffect, useState } from "react";

export default function SystemExplainabilityPanel() {
  const [data, setData] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const API_URL = process.env.REACT_APP_BACKEND_URL || '';
        const res = await fetch(`${API_URL}/api/trading/system/explainability`);
        const json = await res.json();
        setData(json.data || null);
      } catch (e) {
        console.error('[Explainability] Load error:', e);
        setData(null);
      }
    }

    load();
    const i = setInterval(load, 5000);
    return () => clearInterval(i);
  }, []);

  if (!data) {
    return (
      <div className="rounded-xl bg-white border border-[#E5E7EB] p-4">
        <div className="text-sm font-semibold text-neutral-900">System Explainability</div>
        <div className="mt-2 text-xs text-neutral-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="rounded-xl bg-white border border-[#E5E7EB] p-4 space-y-4" data-testid="system-explainability-panel">
      <div>
        <div className="text-sm font-semibold text-neutral-900">System Explainability</div>
        <div className="text-xs text-neutral-500 mt-1">
          Why the system is trading or not trading
        </div>
      </div>

      {/* Mode + Regime */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-lg bg-neutral-50 p-3">
          <div className="text-neutral-500 mb-1">Mode</div>
          <div className="font-semibold text-neutral-900">
            {String(data.mode || "unknown").toUpperCase()}
          </div>
          {data.mode === "bootstrap" && (
            <div className="text-[10px] text-orange-600 mt-1">Exploration phase</div>
          )}
        </div>

        <div className="rounded-lg bg-neutral-50 p-3">
          <div className="text-neutral-500 mb-1">Regime</div>
          <div className="font-semibold text-neutral-900">
            {String(data.regime || "unknown").toUpperCase()}
          </div>
        </div>
      </div>

      {/* Signals */}
      <div className="rounded-lg bg-neutral-50 p-3 text-xs">
        <div className="font-medium text-neutral-900 mb-2">Signals</div>
        <div className="space-y-1 text-neutral-700">
          <div>Generated: <span className="font-semibold">{data.signals?.generated ?? 0}</span></div>
          <div>Hard triggers: <span className="font-semibold">{data.signals?.hard_triggers ?? 0}</span></div>
          <div>Soft fallback: <span className="font-semibold">{data.signals?.soft_fallback_used ? "YES" : "NO"}</span></div>
          {data.signals?.by_strategy && (
            <div className="text-[10px] mt-2 text-neutral-500">
              Trend: {data.signals.by_strategy.trend ?? 0} |
              Breakout: {data.signals.by_strategy.breakout ?? 0} |
              MeanRev: {data.signals.by_strategy.meanrev ?? 0} |
              Soft: {data.signals.by_strategy.soft ?? 0}
            </div>
          )}
        </div>
      </div>

      {/* Ranking */}
      <div className="rounded-lg bg-neutral-50 p-3 text-xs">
        <div className="font-medium text-neutral-900 mb-2">Ranking</div>
        <div className="space-y-1 text-neutral-700">
          <div>Ranked: <span className="font-semibold">{data.ranking?.ranked ?? 0}</span></div>
          <div>Accepted: <span className="font-semibold text-green-600">{data.ranking?.accepted ?? 0}</span></div>
          <div>Rejected: <span className="font-semibold text-red-600">{data.ranking?.rejected ?? 0}</span></div>
          <div>Min score: <span className="font-semibold">{data.ranking?.min_score ?? 0}</span></div>
        </div>
      </div>

      {/* Risk Engine */}
      <div className="rounded-lg bg-neutral-50 p-3 text-xs">
        <div className="font-medium text-neutral-900 mb-2">Risk Engine</div>
        <div className="space-y-1 text-neutral-700">
          <div>Can trade: <span className={`font-semibold ${data.risk?.can_trade ? 'text-green-600' : 'text-red-600'}`}>
            {data.risk?.can_trade ? "YES" : "NO"}
          </span></div>
          <div>Risk multiplier: <span className="font-semibold">{Number(data.risk?.risk_multiplier ?? 0).toFixed(2)}</span></div>
          <div>Reason: <span className="text-[11px]">{data.risk?.reason || "n/a"}</span></div>
        </div>
      </div>

      {/* Allocator */}
      <div className="rounded-lg bg-neutral-50 p-3 text-xs">
        <div className="font-medium text-neutral-900 mb-2">Allocator</div>
        <div className="space-y-1 text-neutral-700">
          <div>Signals in: <span className="font-semibold">{data.allocator?.signals_in ?? 0}</span></div>
          <div>Decisions out: <span className="font-semibold text-blue-600">{data.allocator?.decisions_out ?? 0}</span></div>
          <div>Mode: <span className="font-semibold">{data.allocator?.mode || "n/a"}</span></div>
          <div>Forced fallback: <span className="font-semibold">{data.allocator?.forced_fallback_used ? "YES" : "NO"}</span></div>
          <div className="text-[11px] mt-2 text-neutral-500">Reason: {data.allocator?.reason || "n/a"}</div>
        </div>
      </div>
    </div>
  );
}
