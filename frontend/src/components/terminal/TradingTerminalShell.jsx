import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { TerminalProvider, useTerminal } from "../../store/terminalStore";
import TerminalModuleHeader from "./TerminalModuleHeader";
import TradeWorkspace from "./workspaces/TradeWorkspace";
import PositionsWorkspace from "./workspaces/PositionsWorkspace";
import DecisionsWorkspace from "./workspaces/DecisionsWorkspace";
import AnalyticsWorkspace from "./workspaces/AnalyticsWorkspace";

function WorkspaceRouter() {
  const { state } = useTerminal();

  switch (state.selectedWorkspace) {
    case "trade":
      return <TradeWorkspace />;
    case "positions":
      return <PositionsWorkspace />;
    case "decisions":
      return <DecisionsWorkspace />;
    case "analytics":
      return <AnalyticsWorkspace />;
    default:
      return <TradeWorkspace />;
  }
}

function TradingTerminalContent() {
  const { dispatch } = useTerminal();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab && ["trade", "positions", "decisions", "analytics"].includes(tab)) {
      dispatch({ type: "SET_WORKSPACE", payload: tab });
    }
  }, [searchParams, dispatch]);

  return (
    <div className="w-full h-full flex flex-col bg-[#f5f7fa] text-black" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <TerminalModuleHeader />
      <div className="flex-1 overflow-y-auto p-0">
        <WorkspaceRouter />
      </div>
    </div>
  );
}

export default function TradingTerminalShell() {
  return (
    <TerminalProvider>
      <TradingTerminalContent />
    </TerminalProvider>
  );
}
