import { createContext, useContext, useReducer } from "react";

const TerminalContext = createContext(null);

const initialState = {
  // NAV
  selectedWorkspace: "trade",

  // CORE
  selectedSymbol: "BTCUSDT",
  selectedPositionId: null,
  selectedCase: null, // V4: Trade Case View

  // DATA (заполняется из API)
  positions: [],
  portfolio: null,
  allocator: null,
  execution: null,

  // SYSTEM
  autotradingEnabled: false,
  systemState: "ACTIVE",
  exchangeMode: "PAPER",

  // UI
  chartOverlays: {
    positions: true,
    execution: true,
    allocator: true,
  },
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_SYMBOL":
      return { ...state, selectedSymbol: action.payload };

    case "SET_WORKSPACE":
      return { ...state, selectedWorkspace: action.payload };

    case "SET_SELECTED_CASE":
      return { ...state, selectedCase: action.payload };

    case "SET_POSITIONS":
      return { ...state, positions: action.payload };

    case "SET_PORTFOLIO":
      return { ...state, portfolio: action.payload };

    case "SET_ALLOCATOR":
      return { ...state, allocator: action.payload };

    case "SET_EXECUTION":
      return { ...state, execution: action.payload };

    case "SET_AUTOTRADING":
      return { ...state, autotradingEnabled: action.payload };

    case "SET_SYSTEM_STATE":
      return { ...state, systemState: action.payload };

    case "SET_EXCHANGE_MODE":
      return { ...state, exchangeMode: action.payload };

    default:
      return state;
  }
}

export function TerminalProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  return (
    <TerminalContext.Provider value={{ state, dispatch }}>
      {children}
    </TerminalContext.Provider>
  );
}

export function useTerminal() {
  const ctx = useContext(TerminalContext);
  if (!ctx) throw new Error("useTerminal must be used inside TerminalProvider");
  return ctx;
}
