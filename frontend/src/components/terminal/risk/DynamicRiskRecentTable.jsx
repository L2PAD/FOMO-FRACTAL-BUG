// /app/frontend/src/components/terminal/risk/DynamicRiskRecentTable.jsx
import React from "react";
import { 
  fmtMoney, 
  fmtQty, 
  fmtMultiplier, 
  fmtConfidence, 
  fmtTime 
} from "@/hooks/dynamic_risk/useDynamicRiskRecent";

function StatusBadge({ type, debug }) {
  const isApproved = type === "DYNAMIC_RISK_APPROVED";
  
  // Check if clamped
  const isClamped = debug && (
    Number(debug?.raw_notional) !== Number(debug?.clamped_notional) ||
    Number(debug?.raw_qty) !== Number(debug?.clamped_qty)
  );

  if (isApproved) {
    return (
      <div className="flex gap-2 items-center">
        <span className="px-2 py-1 rounded border text-xs bg-emerald-950/20 text-emerald-400/80 border-emerald-700/50 font-medium">
          APPROVED
        </span>
        {isClamped && (
          <span 
            className="px-2 py-1 rounded border text-xs bg-amber-950/20 text-amber-400/80 border-amber-700/50 font-normal opacity-80"
            title="Size reduced by risk engine"
          >
            CLAMPED
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="flex gap-2 items-center">
      <span className="px-2 py-1 rounded border text-xs bg-red-950/20 text-red-400/80 border-red-700/50 font-medium">
        BLOCKED
      </span>
      {isClamped && (
        <span 
          className="px-2 py-1 rounded border text-xs bg-amber-950/20 text-amber-400/80 border-amber-700/50 font-normal opacity-80"
          title="Size would have been reduced (blocked before execution)"
        >
          CLAMPED
        </span>
      )}
    </div>
  );
}

function R2Badge({ r2Multiplier }) {
  if (!r2Multiplier || r2Multiplier >= 1.0) {
    // No dampening - show muted badge
    return (
      <span className="px-2 py-0.5 rounded text-[10px] bg-gray-800 text-gray-500 border border-gray-700">
        R2 1.0
      </span>
    );
  }

  // Dampening active - show amber/red badge
  const isStrong = r2Multiplier < 0.7;
  const bgColor = isStrong ? "bg-red-950/20" : "bg-amber-950/20";
  const textColor = isStrong ? "text-red-400/80" : "text-amber-400/80";
  const borderColor = isStrong ? "border-red-700/50" : "border-amber-700/50";

  return (
    <span className={`px-2 py-0.5 rounded text-[10px] border ${bgColor} ${textColor} ${borderColor}`}>
      R2 ↓{r2Multiplier.toFixed(2)}
    </span>
  );
}

function DecisionRow({ item, isSelected, onSelect }) {
  const isApproved = item.type === "DYNAMIC_RISK_APPROVED";
  const borderColor = isApproved 
    ? "border-l-green-600" 
    : "border-l-red-600";

  // Extract R2 multiplier from debug (if available)
  const r2Multiplier = item.debug?.r2_multiplier ?? item.r2_multiplier ?? null;

  return (
    <button
      onClick={() => onSelect(item)}
      className={`
        w-full text-left border-l-4 border rounded p-3 transition
        ${borderColor}
        ${
          isSelected
            ? "border-blue-600 bg-blue-950/20"
            : "border-gray-800 hover:border-gray-700 bg-gray-950/40"
        }
      `}
    >
      <div className="grid grid-cols-9 gap-3 text-xs items-center">
        {/* Symbol */}
        <div className="text-white font-medium">
          {item.symbol || "-"}
        </div>

        {/* Status + Clamped Badge */}
        <div>
          <StatusBadge type={item.type} debug={item.debug} />
        </div>

        {/* Confidence - hide for blocked */}
        <div className="text-gray-300">
          {isApproved ? fmtConfidence(item.confidence) : "—"}
        </div>

        {/* Multiplier (R1) - hide for blocked */}
        <div className="text-gray-300">
          {isApproved ? fmtMultiplier(item.size_multiplier) : "—"}
        </div>

        {/* R2 Multiplier - NEW COLUMN */}
        <div>
          {isApproved && r2Multiplier !== null ? (
            <R2Badge r2Multiplier={r2Multiplier} />
          ) : (
            <span className="text-gray-600 text-xs">—</span>
          )}
        </div>

        {/* Final Notional - hide for blocked */}
        <div className="text-white">
          {isApproved ? fmtMoney(item.notional_usd) : "—"}
        </div>

        {/* Qty - hide for blocked */}
        <div className="text-gray-500 text-xs">
          {isApproved ? fmtQty(item.qty) : "—"}
        </div>

        {/* Reason (red if blocked) - with tooltip for long text */}
        <div 
          className={item.reason ? "text-red-400/80 text-xs truncate" : "text-gray-500 text-xs"}
          title={item.reason || ""}
        >
          {item.reason || "—"}
        </div>

        {/* Time */}
        <div className="text-gray-500 text-xs">
          {fmtTime(item.timestamp)}
        </div>
      </div>
    </button>
  );
}

export default function DynamicRiskRecentTable({
  items = [],
  loading,
  selected,
  onSelect,
}) {
  if (loading && items.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded p-6 text-center text-gray-500">
        Loading dynamic risk decisions...
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded p-6 text-center text-gray-500">
        No sizing decisions yet
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <div className="text-white font-semibold">Recent Sizing Decisions</div>
        <div className="text-xs text-gray-500">{items.length} decisions</div>
      </div>

      {/* Column Headers */}
      <div className="grid grid-cols-9 gap-3 text-xs text-gray-400 uppercase tracking-wide mb-2 px-3">
        <div>Symbol</div>
        <div>Status</div>
        <div>Confidence</div>
        <div>Multiplier</div>
        <div>R2</div>
        <div>Notional</div>
        <div>Qty</div>
        <div>Reason</div>
        <div>Time</div>
      </div>

      {/* Rows */}
      <div className="space-y-2 max-h-[500px] overflow-y-auto">
        {items.map((item, i) => {
          const key = `${item.symbol || "x"}-${item.timestamp || i}-${item.type || "y"}`;
          const isSelected =
            selected &&
            selected.timestamp === item.timestamp &&
            selected.symbol === item.symbol &&
            selected.type === item.type;

          return (
            <DecisionRow
              key={key}
              item={item}
              isSelected={isSelected}
              onSelect={onSelect}
            />
          );
        })}
      </div>
    </div>
  );
}
