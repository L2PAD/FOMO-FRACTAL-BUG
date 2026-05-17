export default function AdaptiveRiskAnalyticsPanel({ data, loading }) {
  if (loading) {
    return (
      <div className="p-4 bg-gray-900 rounded-xl border border-gray-800">
        <div className="text-xs text-gray-400 mb-2 uppercase">Adaptive Risk (R2)</div>
        <div className="text-xs text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!data) return null;

  const {
    activation_rate_pct,
    avg_r2_multiplier,
    avg_drawdown_component,
    avg_loss_streak_component,
  } = data;

  return (
    <div className="p-4 bg-gray-900 rounded-xl border border-gray-800">
      <div className="text-xs text-gray-400 mb-3 uppercase tracking-wide">
        Adaptive Risk (R2)
      </div>

      {/* 1. Activation Rate - главный вопрос */}
      <div className="flex justify-between mb-3 pb-3 border-b border-gray-800">
        <span className="text-gray-400 text-sm">Activation</span>
        <span className="text-amber-300 font-bold text-base">
          {activation_rate_pct ?? 0}%
        </span>
      </div>

      {/* 2. Avg Multiplier - насколько режет */}
      <div className="flex justify-between mb-3">
        <span className="text-gray-400 text-sm">Avg Multiplier</span>
        <span className="text-white font-medium">
          {avg_r2_multiplier !== null ? avg_r2_multiplier.toFixed(3) : "—"}
        </span>
      </div>

      {/* 3. Components - причина */}
      <div className="space-y-2 text-xs">
        <div className="flex justify-between">
          <span className="text-gray-500">Drawdown</span>
          <span className="text-gray-300">
            {avg_drawdown_component !== null ? avg_drawdown_component.toFixed(3) : "—"}
          </span>
        </div>

        <div className="flex justify-between">
          <span className="text-gray-500">Loss Streak</span>
          <span className="text-gray-300">
            {avg_loss_streak_component !== null ? avg_loss_streak_component.toFixed(3) : "—"}
          </span>
        </div>
      </div>

      {/* Explanation if no data */}
      {activation_rate_pct === 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800 text-[10px] text-gray-500">
          No adaptive risk events yet
        </div>
      )}
    </div>
  );
}
