// /app/frontend/src/components/terminal/risk/DynamicRiskStatsBar.jsx
import React from "react";

function StatCard({ label, value, tone = "default", subtitle = null }) {
  const toneClass =
    tone === "green"
      ? "text-green-300"
      : tone === "red"
      ? "text-red-300"
      : tone === "amber"
      ? "text-amber-300"
      : "text-white";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      <div className="text-xs text-gray-400 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${toneClass}`}>
        {value ?? "-"}
      </div>
      {subtitle && (
        <div className="text-xs text-gray-500 mt-1">{subtitle}</div>
      )}
    </div>
  );
}

export default function DynamicRiskStatsBar({ stats, loading }) {
  if (loading && !stats) {
    return (
      <div className="grid grid-cols-5 gap-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="bg-gray-900 border border-gray-800 rounded p-4 text-gray-500 text-sm"
          >
            Loading...
          </div>
        ))}
      </div>
    );
  }

  const approved = stats?.approved_count ?? 0;
  const blocked = stats?.blocked_count ?? 0;
  const avgMultiplier = stats?.avg_multiplier ?? 0;
  const avgNotional = stats?.avg_notional_usd ?? 0;
  const topReason = stats?.top_block_reasons?.[0];

  // Map reasons to hints
  const reasonHints = {
    "MAX_PORTFOLIO_EXPOSURE": "Portfolio > 30%",
    "MAX_SYMBOL_EXPOSURE": "Symbol limit hit",
    "CONFIDENCE_TOO_LOW": "Confidence < 0.55",
    "NO_CONFIDENCE": "Missing confidence",
  };

  const hint = topReason?.reason ? reasonHints[topReason.reason] : null;

  return (
    <div className="grid grid-cols-5 gap-4">
      <StatCard label="Approved" value={approved} tone="green" />
      <StatCard label="Blocked" value={blocked} tone="red" />
      <StatCard 
        label="Avg Multiplier" 
        value={`${avgMultiplier.toFixed(2)}x`} 
        tone="amber" 
      />
      <StatCard 
        label="Avg Notional" 
        value={`$${avgNotional.toFixed(2)}`} 
      />
      <StatCard
        label="Top Block Reason"
        value={topReason?.reason || "None"}
        subtitle={topReason ? `${topReason.count} times${hint ? ` → ${hint}` : ''}` : null}
        tone={topReason ? "red" : "default"}
      />
    </div>
  );
}
