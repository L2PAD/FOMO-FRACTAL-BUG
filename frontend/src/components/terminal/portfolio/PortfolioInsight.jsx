import { useMemo } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function PortfolioInsight() {
  const { state } = useTerminal();

  const portfolio = state.portfolio || {};
  const positions = state.positions || [];
  const riskHeat = portfolio.risk_heat || 0;
  const equity = portfolio.equity || 10000;

  // Calculate insights
  const insight = useMemo(() => {
    // Check concentration
    const exposureMap = {};
    positions.forEach(p => {
      const symbol = p.symbol.replace("USDT", "");
      const sizeUsd = Number(p.size_usd || 0);
      exposureMap[symbol] = (exposureMap[symbol] || 0) + sizeUsd;
    });

    const maxExposure = Object.values(exposureMap).reduce((max, val) => Math.max(max, val), 0);
    const maxExposurePct = equity > 0 ? (maxExposure / equity) * 100 : 0;
    const maxSymbol = Object.keys(exposureMap).find(k => exposureMap[k] === maxExposure) || "";

    // High concentration
    if (maxExposurePct > 40) {
      return {
        type: "warning",
        title: `High ${maxSymbol} concentration`,
        message: "→ Consider reducing exposure to avoid correlated drawdown"
      };
    }

    // High risk heat
    if (riskHeat > 0.7) {
      return {
        type: "warning",
        title: "Elevated portfolio risk",
        message: "→ Consider reducing position sizes or closing weakest positions"
      };
    }

    // Multiple positions
    if (positions.length > 5) {
      return {
        type: "info",
        title: "High position count",
        message: "→ Managing many positions increases complexity"
      };
    }

    // No positions
    if (positions.length === 0) {
      return {
        type: "neutral",
        title: "No active positions",
        message: "→ Waiting for high-quality setups"
      };
    }

    // All good
    return {
      type: "success",
      title: "Portfolio balanced",
      message: "→ Risk and exposure within safe limits"
    };
  }, [portfolio, positions, riskHeat, equity]);

  const colors = {
    warning: "bg-orange-50 border-orange-200 text-orange-700",
    info: "bg-blue-50 border-blue-200 text-blue-700",
    success: "bg-green-50 border-green-200 text-green-700",
    neutral: "bg-neutral-50 border-neutral-200 text-neutral-600"
  };

  const icons = {
    warning: "⚠️",
    info: "ℹ️",
    success: "✓",
    neutral: "—"
  };

  return (
    <div className={`rounded-xl p-4 border ${colors[insight.type]}`} data-testid="portfolio-insight">
      <div className="text-xs font-semibold mb-2">
        {icons[insight.type]} PORTFOLIO INSIGHT
      </div>

      <div className="text-sm font-medium text-neutral-900 mb-1">
        {insight.title}
      </div>

      <div className="text-xs text-neutral-700">
        {insight.message}
      </div>
    </div>
  );
}
