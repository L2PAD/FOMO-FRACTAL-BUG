// /app/frontend/src/components/terminal/risk/DynamicRiskExplainPanel.jsx
import React from "react";
import { fmtMoney, fmtQty, fmtMultiplier, fmtConfidence } from "@/hooks/dynamic_risk/useDynamicRiskRecent";

function interpretR2(r2) {
  if (r2 >= 1) return "No dampening";
  if (r2 >= 0.8) return "Slight risk reduction";
  if (r2 >= 0.6) return "Moderate risk reduction";
  return "Aggressive risk reduction";
}

function Row({ label, value, tone = "default" }) {
  const toneClass =
    tone === "secondary"
      ? "text-gray-500"
      : tone === "red"
      ? "text-red-300"
      : "text-white";

  return (
    <div className="flex justify-between text-[11px] py-0.5">
      <span className="text-gray-400">{label}</span>
      <span className={toneClass}>{value ?? "-"}</span>
    </div>
  );
}

function ClampRow({ label, raw, clamped, showDelta = false }) {
  // Handle missing data
  if (raw == null || clamped == null) {
    return <Row label={label} value="—" tone="secondary" />;
  }

  const rawNum = Number(raw);
  const clampedNum = Number(clamped);
  const isDifferent = Math.abs(rawNum - clampedNum) > 0.0001;

  if (!isDifferent) {
    // Equal - show single value
    return <Row label={label} value={clamped} />;
  }

  // Calculate delta
  const delta = clampedNum - rawNum;
  const deltaPct = ((delta / rawNum) * 100).toFixed(1);
  const deltaStr = showDelta ? ` (Δ ${delta > 0 ? '+' : ''}${delta.toFixed(2)}, ${deltaPct}%)` : '';

  // Different - highlight transition
  return (
    <div className="flex justify-between text-[11px] py-0.5">
      <span className="text-gray-400">{label}</span>
      <div className="text-right">
        <span className="text-amber-300 font-medium">
          {raw} → {clamped}
        </span>
        {showDelta && delta < 0 && (
          <div className="text-[10px] text-amber-400 mt-0.5">
            Δ {delta.toFixed(2)} ({deltaPct}%)
          </div>
        )}
      </div>
    </div>
  );
}

function SectionDivider() {
  return <div className="border-t border-gray-800 my-3" />;
}

export default function DynamicRiskExplainPanel({ item }) {
  if (!item) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded p-4 text-center text-gray-500">
        Select a decision to inspect sizing explainability
      </div>
    );
  }

  const debug = item.debug || {};
  const isBlocked = item.type === "DYNAMIC_RISK_BLOCKED";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded p-4 space-y-2">
      {/* Header */}
      <div className="flex justify-between items-center pb-2 border-b border-gray-800">
        <div className="text-white font-semibold">Sizing Explainability</div>
        <div className={isBlocked ? "text-red-300 text-xs font-medium" : "text-green-300 text-xs font-medium"}>
          {isBlocked ? "BLOCKED" : "APPROVED"}
        </div>
      </div>

      {/* Section 1: Final Decision */}
      <div className="space-y-0.5">
        <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">
          Final Decision
        </div>
        <Row label="Status" value={isBlocked ? "BLOCKED" : "APPROVED"} />
        <Row 
          label="Reason" 
          value={item.reason || "APPROVED"} 
          tone={item.reason ? "red" : "secondary"} 
        />
        <Row label="Final Notional" value={fmtMoney(item.notional_usd)} />
        <Row label="Final Qty" value={fmtQty(item.qty)} />
        <Row label="Final Multiplier" value={fmtMultiplier(item.size_multiplier)} />
      </div>

      <SectionDivider />

      {/* Section 2: RAW → CLAMPED (highlighted) */}
      <div className="space-y-0.5">
        <div className="text-xs text-amber-300 uppercase tracking-wide mb-2">
          Raw → Clamped
        </div>
        <ClampRow
          label="Notional"
          raw={fmtMoney(debug.raw_notional)}
          clamped={fmtMoney(debug.clamped_notional)}
          showDelta={true}
        />
        <ClampRow
          label="Qty"
          raw={fmtQty(debug.raw_qty)}
          clamped={fmtQty(debug.clamped_qty)}
          showDelta={false}
        />
      </div>

      <SectionDivider />

      {/* Section 3: Components */}
      <div className="space-y-0.5">
        <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">
          Components
        </div>
        <Row label="Base Notional" value={fmtMoney(debug.base_notional)} tone="secondary" />
        <Row label="Confidence" value={fmtConfidence(item.confidence)} tone="secondary" />
        <Row label="Confidence Component" value={fmtMultiplier(debug.confidence_component)} tone="secondary" />
        <Row label="Regime" value={debug.regime || "-"} tone="secondary" />
        <Row label="Regime Component" value={fmtMultiplier(debug.regime_component)} tone="secondary" />
      </div>

      {/* Section 4: ADAPTIVE RISK (R2) */}
      {debug.r2_multiplier !== undefined && (
        <>
          <SectionDivider />
          <div className="space-y-0.5">
            <div className="text-xs text-amber-300 uppercase tracking-wide mb-2">
              Adaptive Risk (R2)
            </div>
            
            {/* R2 Components */}
            <div className="space-y-2 bg-gray-950/40 rounded p-3">
              {/* Drawdown Component */}
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Drawdown</span>
                <div className="text-right">
                  <span className="text-gray-300">
                    {debug.r2_debug?.drawdown_pct !== undefined 
                      ? `${debug.r2_debug.drawdown_pct.toFixed(2)}%` 
                      : "—"
                    }
                    {" → "}
                  </span>
                  <span className={
                    debug.r2_components?.drawdown < 1 
                      ? "text-amber-300 font-medium" 
                      : "text-gray-300"
                  }>
                    {debug.r2_components?.drawdown !== undefined
                      ? fmtMultiplier(debug.r2_components.drawdown)
                      : "—"
                    }
                  </span>
                </div>
              </div>

              {/* Loss Streak Component */}
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Loss Streak</span>
                <div className="text-right">
                  <span className="text-gray-300">
                    {debug.r2_debug?.loss_streak_count !== undefined
                      ? debug.r2_debug.loss_streak_count
                      : "—"
                    }
                    {" → "}
                  </span>
                  <span className={
                    debug.r2_components?.loss_streak < 1
                      ? "text-amber-300 font-medium"
                      : "text-gray-300"
                  }>
                    {debug.r2_components?.loss_streak !== undefined
                      ? fmtMultiplier(debug.r2_components.loss_streak)
                      : "—"
                    }
                  </span>
                </div>
              </div>

              {/* Divider */}
              <div className="border-t border-gray-800 my-2" />

              {/* R2 Final Multiplier + Interpretation */}
              <div className="flex flex-col gap-1 pt-1">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">R2 Multiplier</span>
                  <span className={
                    debug.r2_multiplier < 1
                      ? "text-amber-300 font-semibold text-white"
                      : "text-gray-300"
                  }>
                    {fmtMultiplier(debug.r2_multiplier)}
                  </span>
                </div>
                <div className="text-[11px] text-gray-500 text-right">
                  {interpretR2(debug.r2_multiplier)}
                </div>
              </div>

              {/* Final Multiplier (R1 × R2) */}
              {debug.final_multiplier !== undefined && (
                <div className="flex justify-between text-sm border-t border-gray-800 pt-2 mt-2">
                  <span className="text-gray-400">Final (R1 × R2)</span>
                  <span className="text-white font-semibold">
                    {fmtMultiplier(debug.final_multiplier)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
