import { useTerminal } from "../../store/terminalStore";

export default function TerminalTopbar() {
  const { state } = useTerminal();

  return (
    <div className="h-12 flex items-center justify-between px-4 border-b border-neutral-200">
      <div className="font-semibold text-sm">TRADING TERMINAL</div>

      <div className="flex items-center gap-4 text-xs">
        <span className="font-mono font-semibold">{state.selectedSymbol}</span>
        <span className="px-2 py-1 rounded bg-neutral-100 text-neutral-700">{state.exchangeMode}</span>
        <span className={`px-2 py-1 rounded ${state.autotradingEnabled ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {state.autotradingEnabled ? "AUTO ON" : "AUTO OFF"}
        </span>
        <span className="text-neutral-500">{state.systemState}</span>
      </div>
    </div>
  );
}
