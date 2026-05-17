// Runtime Status Panel — Runtime Control Layer Status

import React from 'react';
import { Cpu, Circle } from 'lucide-react';
import { useRuntimeState } from '../../../hooks/runtime/useRuntimeState';

export default function RuntimeStatusPanel() {
  const { data, error, loading } = useRuntimeState();
  
  const formatTimestamp = (ts) => {
    if (!ts) return 'Never';
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString('en-US', { hour12: false });
  };
  
  const formatNextRun = (ts) => {
    if (!ts) return '—';
    const now = Math.floor(Date.now() / 1000);
    const delta = ts - now;
    if (delta <= 0) return 'Now';
    return `${delta}s`;
  };
  
  const isEnabled = data?.enabled ?? false;
  const mode = data?.mode || 'MANUAL';
  const status = data?.status || 'IDLE';
  
  const getStatusColor = () => {
    if (!isEnabled) return 'text-neutral-500';
    if (status === 'RUNNING') return 'text-blue-600';
    if (status === 'ERROR') return 'text-red-600';
    return 'text-green-600';
  };
  
  const getStatusBg = () => {
    if (!isEnabled) return 'bg-neutral-50';
    if (status === 'RUNNING') return 'bg-blue-50';
    if (status === 'ERROR') return 'bg-red-50';
    return 'bg-green-50';
  };
  
  const getModeColor = () => {
    if (mode === 'AUTO') return 'text-red-600';
    if (mode === 'SEMI_AUTO') return 'text-orange-600';
    return 'text-neutral-700';
  };
  
  return (
    <div 
      className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow duration-200" 
      data-testid="runtime-status-panel"
      style={{ fontFamily: 'Gilroy, sans-serif' }}
    >
      {/* Header */}
      <div className="px-4 py-3 bg-neutral-50 border-b border-neutral-200">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-neutral-700 uppercase tracking-wider">
            RUNTIME STATUS
          </h3>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-3">
        {error && (
          <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
            <span className="text-xs text-red-700">{error}</span>
          </div>
        )}
        
        {loading && !data && (
          <div className="text-xs text-neutral-500">Loading runtime state...</div>
        )}
        
        {data && (
          <>
            {/* Status Card */}
            <div className={`px-3 py-2 rounded-lg border ${getStatusBg()} ${
              !isEnabled ? 'border-neutral-200' : 
              status === 'RUNNING' ? 'border-blue-200' : 
              status === 'ERROR' ? 'border-red-200' : 
              'border-green-200'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-neutral-600">RUNTIME</span>
                <div className="flex items-center gap-2">
                  <Circle className={`w-2 h-2 fill-current ${getStatusColor()}`} />
                  <span className={`text-sm font-bold ${getStatusColor()}`}>
                    {!isEnabled ? 'STOPPED' : status}
                  </span>
                </div>
              </div>
            </div>
            
            {/* Mode */}
            <div className="flex items-center justify-between py-2 border-b border-neutral-100">
              <span className="text-xs font-semibold text-neutral-600">MODE</span>
              <span className={`text-sm font-bold ${getModeColor()}`}>
                {mode}
              </span>
            </div>
            
            {/* Loop Interval */}
            <div className="flex items-center justify-between py-2 border-b border-neutral-100">
              <span className="text-xs font-semibold text-neutral-600">LOOP INTERVAL</span>
              <span className="text-sm font-bold text-neutral-900">
                {data.loop_interval_sec}s
              </span>
            </div>
            
            {/* Symbols */}
            <div className="flex items-center justify-between py-2 border-b border-neutral-100">
              <span className="text-xs font-semibold text-neutral-600">SYMBOLS</span>
              <span className="text-sm font-bold text-neutral-900">
                {data.symbols?.join(', ') || '—'}
              </span>
            </div>
            
            {/* Timestamps */}
            <div className="pt-2 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">Last Run</span>
                <span className="text-xs font-mono text-neutral-700">
                  {formatTimestamp(data.last_run_at)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">Next Run</span>
                <span className="text-xs font-mono text-neutral-700">
                  {formatNextRun(data.next_run_at)}
                </span>
              </div>
              {data.last_error && (
                <div className="flex items-start gap-2 pt-1">
                  <span className="text-xs text-neutral-500">Error:</span>
                  <span className="text-xs text-red-600 flex-1">
                    {data.last_error}
                  </span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
