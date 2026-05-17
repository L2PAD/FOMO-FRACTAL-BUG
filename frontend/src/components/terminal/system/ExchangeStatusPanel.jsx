// Exchange Status Panel

import React from 'react';
import { Globe, Circle, Wifi } from 'lucide-react';

export default function ExchangeStatusPanel({ exchangeStatus, exchangeHealth }) {
  const mode = exchangeStatus?.mode || 'UNKNOWN';
  const connected = exchangeStatus?.connected ?? false;
  const accountId = exchangeStatus?.account_id || 'N/A';
  const canTrade = exchangeStatus?.can_trade ?? false;
  
  const latency = exchangeHealth?.latency_ms || 0;
  const lastSyncSeconds = exchangeHealth?.last_sync_seconds;
  
  const formatSyncTime = (seconds) => {
    if (seconds === null || seconds === undefined) return 'Unknown';
    if (seconds < 60) return `${seconds}s ago`;
    return `${Math.floor(seconds / 60)}m ago`;
  };
  
  const getLatencyColor = () => {
    if (latency < 100) return 'text-green-700';
    if (latency < 200) return 'text-yellow-700';
    return 'text-red-700';
  };
  
  return (
    <div 
      className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow duration-200" 
      data-testid="exchange-status-panel"
      style={{ fontFamily: 'Gilroy, sans-serif' }}
    >
      {/* Header */}
      <div className="px-4 py-3 bg-neutral-50 border-b border-neutral-200">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-neutral-700 uppercase tracking-wider">
            EXCHANGE
          </h3>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Connection Status Card */}
        <div className={`px-3 py-2 rounded-lg border ${connected ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-600">CONNECTION</span>
            <div className="flex items-center gap-2">
              <Circle className={`w-2 h-2 fill-current ${connected ? 'text-green-700' : 'text-red-700'}`} />
              <span className={`text-sm font-bold ${connected ? 'text-green-700' : 'text-red-700'}`}>
                {connected ? 'CONNECTED' : 'DISCONNECTED'}
              </span>
            </div>
          </div>
        </div>
        
        {/* Mode */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">MODE</span>
          <span className="text-sm font-bold text-neutral-900">{mode}</span>
        </div>
        
        {/* Account */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">ACCOUNT</span>
          <span className="text-xs font-mono text-neutral-700 truncate max-w-[180px]">{accountId}</span>
        </div>
        
        {/* Can Trade */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">CAN TRADE</span>
          <span className={`text-sm font-bold ${canTrade ? 'text-green-700' : 'text-red-700'}`}>
            {canTrade ? 'YES' : 'NO'}
          </span>
        </div>
        
        {/* Health Metrics */}
        <div className="pt-2 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Wifi className="w-3 h-3 text-neutral-500" />
              <span className="text-xs text-neutral-500">Latency</span>
            </div>
            <span className={`text-xs font-mono font-bold ${getLatencyColor()}`}>
              {latency}ms
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-500">Last Sync</span>
            <span className="text-xs font-mono text-neutral-700">{formatSyncTime(lastSyncSeconds)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
