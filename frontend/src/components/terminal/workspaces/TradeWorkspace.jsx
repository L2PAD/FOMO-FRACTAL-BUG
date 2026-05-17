import { useEffect } from "react";
import SmartChartPanel from "../panels/SmartChartPanel";
import TradeExplainabilityStrip from "../panels/TradeExplainabilityStrip";
import CaseRailCompact from "../trade-case/CaseRailCompact";
import CaseCommandHeaderUltraCompact from "../trade-case/CaseCommandHeaderUltraCompact";
import ExecutionFeed from "../ExecutionFeed";
import { useTerminal } from "../../../store/terminalStore";
import { useTradingCases } from "../../../hooks/useTradingCases";

export default function TradeWorkspace() {
  const { state, dispatch } = useTerminal();
  const { cases: realCases } = useTradingCases();

  useEffect(() => {
    if (!state.selectedCase && realCases.length > 0) {
      dispatch({ type: "SET_SELECTED_CASE", payload: realCases[0] });
    }
  }, [state.selectedCase, dispatch, realCases]);

  const selectedCase = state.selectedCase;

  return (
    <div className="flex flex-col h-full" data-testid="trade-workspace" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      {/* TOP: System Bar — borderless, lets the pills carry the contrast */}
      <div className="px-4 pt-2 pb-1 flex-shrink-0 bg-white">
        <TradeExplainabilityStrip />
      </div>

      {/* MAIN: Sidebar + Chart — single thin separator only */}
      <div className="flex flex-1 min-h-0 overflow-hidden border-t border-gray-100">
        {/* LEFT SIDEBAR: Opportunities — fixed width */}
        <div className="w-[260px] flex-shrink-0 border-r border-gray-100 bg-white overflow-y-auto">
          <CaseRailCompact />
        </div>

        {/* RIGHT: Header + Chart + Activity — flex column */}
        <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
          {/* Case Header — directional tone bar lives inside the component */}
          <div className="flex-shrink-0 bg-white border-b border-gray-100">
            <CaseCommandHeaderUltraCompact caseData={selectedCase} />
          </div>

          {/* Chart — takes remaining space */}
          <div className="flex-1 min-h-0 relative">
            <SmartChartPanel hideNoTradeOverlay={true} />
          </div>

          {/* Activity Feed — fixed at bottom */}
          <div className="flex-shrink-0 border-t border-gray-100 bg-white max-h-[150px] overflow-y-auto">
            <ExecutionFeed />
          </div>
        </div>
      </div>
    </div>
  );
}
