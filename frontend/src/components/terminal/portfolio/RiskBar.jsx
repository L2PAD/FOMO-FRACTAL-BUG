import { useTerminal } from "../../../store/terminalStore";

export default function RiskBar() {
  const { state } = useTerminal();

  const riskHeat = state.portfolio?.risk_heat || 0;
  const percent = Math.round(riskHeat * 100);

  // Color based on risk level
  const barColor = 
    percent > 70 ? "bg-red-500" :
    percent > 50 ? "bg-orange-500" :
    "bg-green-500";

  const message = 
    percent > 70 ? "→ High risk — drawdown sensitivity increased" :
    percent > 50 ? "→ Elevated risk — monitor closely" :
    "→ Safe risk zone";

  return (
    <div className="bg-white rounded-xl p-4 border border-neutral-200" data-testid="risk-bar">
      <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
        RISK HEAT
      </div>

      <div className="flex items-center gap-3 mb-2">
        {/* Bar */}
        <div className="flex-1 h-2 bg-neutral-200 rounded-full overflow-hidden">
          <div 
            className={`h-full ${barColor} transition-all duration-300`}
            style={{ width: `${percent}%` }}
          />
        </div>

        {/* Percentage */}
        <div className="text-sm font-bold text-neutral-900 font-mono tabular-nums min-w-[45px] text-right" data-testid="risk-heat-value">
          {percent}%
        </div>
      </div>

      {/* Message */}
      <div className="text-xs text-neutral-600 mt-2">
        {message}
      </div>
    </div>
  );
}
