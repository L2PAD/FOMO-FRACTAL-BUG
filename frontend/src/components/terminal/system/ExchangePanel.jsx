import { useState } from "react";
import { useTerminal } from "../../../store/terminalStore";

export default function ExchangePanel() {
  const { state } = useTerminal();
  const [apiKeyStatus, setApiKeyStatus] = useState("CONNECTED");

  return (
    <div className="border border-neutral-200 rounded-lg p-4">
      <div className="mb-4 font-semibold text-neutral-900">Exchange</div>

      <div className="space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-neutral-600">Exchange:</span>
          <span className="font-semibold">Binance</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Mode:</span>
          <span className="font-semibold">{state.exchangeMode}</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">API Key:</span>
          <span className="text-green-600 font-semibold">{apiKeyStatus}</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">WebSocket:</span>
          <span className="text-green-600 font-semibold">CONNECTED</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Price Stream:</span>
          <span className="text-green-600 font-semibold">ACTIVE</span>
        </div>

        <div className="flex justify-between">
          <span className="text-neutral-600">Fill Sync:</span>
          <span className="text-green-600 font-semibold">ACTIVE</span>
        </div>
      </div>
    </div>
  );
}
