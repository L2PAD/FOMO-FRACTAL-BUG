import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function PortfolioHero() {
  const { state } = useTerminal();

  const portfolio = state.portfolio || {};
  const equity = portfolio.equity || 10000;
  const totalPnl = portfolio.total_pnl || 0;
  const totalPnlPct = equity > 0 ? (totalPnl / equity) * 100 : 0;

  const pnlColor = totalPnl >= 0 ? "text-green-600" : "text-red-600";
  const pnlSign = totalPnl >= 0 ? "+" : "";

  // Status message
  const statusMessage = useMemo(() => {
    const riskHeat = portfolio.risk_heat || 0;
    const drawdown = Math.abs(portfolio.drawdown_pct || 0);

    if (drawdown > 10) {
      return "⚠️ Elevated drawdown — recovery mode";
    }
    if (riskHeat > 0.7) {
      return "→ High risk exposure — caution advised";
    }
    if (totalPnl > 0 && riskHeat < 0.5) {
      return "→ Controlled growth with moderate risk";
    }
    if (totalPnl > 0) {
      return "→ Profitable with elevated risk exposure";
    }
    return "→ Capital preservation mode";
  }, [portfolio, totalPnl]);

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-neutral-200" data-testid="portfolio-hero">
      <div className="text-xs font-semibold text-neutral-500 mb-3 tracking-wide">
        PORTFOLIO STATUS
      </div>

      <div className="flex justify-between items-end mb-4">
        {/* Equity */}
        <div>
          <div className="text-3xl font-bold text-neutral-900 font-mono tabular-nums" data-testid="portfolio-equity">
            ${equity.toFixed(0)}
          </div>
          <div className="text-sm text-neutral-500 mt-1">
            Equity
          </div>
        </div>

        {/* PnL */}
        <div className="text-right">
          <div className={`${pnlColor} font-bold text-xl font-mono tabular-nums`} data-testid="portfolio-pnl">
            {pnlSign}${Math.abs(totalPnl).toFixed(0)} ({pnlSign}{totalPnlPct.toFixed(2)}%)
          </div>
          <div className="text-xs text-neutral-400 mt-1">
            Total PnL
          </div>
        </div>
      </div>

      {/* Status */}
      <div className="pt-3 border-t border-neutral-200">
        <div className="text-sm text-neutral-700">
          {statusMessage}
        </div>
      </div>
    </div>
  );
}
