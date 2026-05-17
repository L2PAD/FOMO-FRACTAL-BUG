import { useTerminal } from "../../store/terminalStore";

const tabs = [
  { id: "trade", label: "TRADE" },
  { id: "portfolio", label: "PORTFOLIO" },
  { id: "strategies", label: "STRATEGIES" },
  { id: "execution", label: "EXECUTION" },
  { id: "system", label: "SYSTEM" },
  { id: "analytics", label: "ANALYTICS" }
];

export default function TerminalTabs() {
  const { state, dispatch } = useTerminal();

  return (
    <div className="h-10 flex items-center gap-1 px-4 border-b border-neutral-200 bg-white">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => dispatch({ type: "SET_WORKSPACE", payload: tab.id })}
          className={`
            px-4 py-2 text-xs font-medium rounded-t transition-colors
            ${
              state.selectedWorkspace === tab.id
                ? "bg-white text-neutral-900 border-b-2 border-neutral-900"
                : "bg-transparent text-neutral-500 hover:text-neutral-700 hover:bg-neutral-50"
            }
          `}
          data-testid={`tab-${tab.id}`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
