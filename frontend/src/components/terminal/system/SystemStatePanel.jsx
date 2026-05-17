// System State Panel

import React from 'react';
import { Activity, Circle } from 'lucide-react';

export default function SystemStatePanel({ systemState }) {
  const mode = systemState?.mode || 'MANUAL';
  const running = systemState?.running ?? false;
  const killSwitch = systemState?.kill_switch ?? false;
  const lastDecisionTs = systemState?.last_decision_ts;
  const lastTradeTs = systemState?.last_trade_ts;
  const loopActive = systemState?.loop_active ?? false;
  
  const formatTimestamp = (ts) => {
    if (!ts) return 'Never';
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };
  
  const getStatusColor = () => {
    if (killSwitch) return 'text-red-700';
    if (!running) return 'text-neutral-500';
    return 'text-green-700';
  };
  
  const getStatusBg = () => {
    if (killSwitch) return 'bg-red-50';
    if (!running) return 'bg-neutral-50';
    return 'bg-green-50';
  };
  
  return (
    <div 
      className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow duration-200" 
      data-testid="system-state-panel"
      style={{ fontFamily: 'Gilroy, sans-serif' }}
    >
      {/* Header */}
      <div className="px-4 py-3 bg-neutral-50 border-b border-neutral-200">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-neutral-700 uppercase tracking-wider">
            SYSTEM STATE
          </h3>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Status Card */}
        <div className={`px-3 py-2 rounded-lg border ${getStatusBg()} ${killSwitch ? 'border-red-200' : running ? 'border-green-200' : 'border-neutral-200'}`}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-600">STATUS</span>
            <div className="flex items-center gap-2">
              <Circle className={`w-2 h-2 fill-current ${getStatusColor()}`} />
              <span className={`text-sm font-bold ${getStatusColor()}`}>
                {killSwitch ? 'STOPPED' : (running ? 'RUNNING' : 'IDLE')}
              </span>
            </div>
          </div>
        </div>
        
        {/* Mode */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">MODE</span>
          <span className="text-sm font-bold text-neutral-900">{mode}</span>
        </div>
        
        {/* Kill Switch */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">KILL SWITCH</span>
          <span className={`text-sm font-bold ${killSwitch ? 'text-red-700' : 'text-neutral-500'}`}>
            {killSwitch ? 'ACTIVE' : 'OFF'}
          </span>
        </div>
        
        {/* Loop Status */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">LOOP STATUS</span>
          <div className="flex items-center gap-2">
            {loopActive && <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />}
            <span className={`text-sm font-bold ${loopActive ? 'text-green-700' : 'text-neutral-500'}`}>
              {loopActive ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>
        </div>
        
        {/* Timestamps */}
        <div className="pt-2 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-500">Last Decision</span>
            <span className="text-xs font-mono text-neutral-700">{formatTimestamp(lastDecisionTs)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-500">Last Trade</span>
            <span className="text-xs font-mono text-neutral-700">{formatTimestamp(lastTradeTs)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
