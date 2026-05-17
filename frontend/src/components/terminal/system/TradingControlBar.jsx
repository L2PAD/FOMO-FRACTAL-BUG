// Trading Control Bar — Kill Switch + Mode + Actions

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Power, PowerOff, RefreshCw, Zap, Play, Square, RotateCw } from 'lucide-react';
import { toast } from 'sonner';
import { useRuntimeActions } from '../../../hooks/runtime/useRuntimeActions';
import { useRuntimeState } from '../../../hooks/runtime/useRuntimeState';

const backendUrl = process.env.REACT_APP_BACKEND_URL;

export default function TradingControlBar({ systemState, onUpdate }) {
  const [loading, setLoading] = useState(false);
  const runtimeActions = useRuntimeActions();
  const { data: runtimeState } = useRuntimeState();
  
  const isKillSwitchActive = systemState?.kill_switch || false;
  const currentMode = systemState?.mode || 'MANUAL';
  
  const isRuntimeEnabled = runtimeState?.enabled ?? false;
  const runtimeMode = runtimeState?.mode || 'MANUAL';
  
  // Kill Switch toggle
  const handleKillSwitch = async () => {
    setLoading(true);
    
    try {
      const endpoint = isKillSwitchActive
        ? `${backendUrl}/api/strategy/kill-switch/deactivate`
        : `${backendUrl}/api/strategy/kill-switch/activate`;
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: 'Manual toggle' })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        toast.success(data.message);
        onUpdate();
      } else {
        toast.error('Kill switch toggle failed');
      }
    } catch (error) {
      toast.error('Failed to toggle kill switch');
    } finally {
      setLoading(false);
    }
  };
  
  // Mode change (old system mode)
  const handleModeChange = async (newMode) => {
    setLoading(true);
    
    try {
      const response = await fetch(`${backendUrl}/api/system/mode`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        toast.success(`Mode set to ${newMode}`);
        onUpdate();
      } else {
        toast.error('Mode change failed');
      }
    } catch (error) {
      toast.error('Failed to change mode');
    } finally {
      setLoading(false);
    }
  };
  
  // Force sync
  const handleForceSync = async () => {
    setLoading(true);
    
    try {
      const response = await fetch(`${backendUrl}/api/exchange/sync`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.ok) {
        toast.success('Exchange sync complete');
        onUpdate();
      } else {
        toast.error('Sync failed');
      }
    } catch (error) {
      toast.error('Failed to sync');
    } finally {
      setLoading(false);
    }
  };
  
  // Runtime controls
  const handleRuntimeStart = async () => {
    await runtimeActions.startRuntime();
  };
  
  const handleRuntimeStop = async () => {
    await runtimeActions.stopRuntime();
  };
  
  const handleRunOnce = async () => {
    await runtimeActions.runOnce();
  };
  
  const handleRuntimeModeChange = async (newMode) => {
    await runtimeActions.setMode(newMode);
  };
  
  return (
    <div 
      className="px-4 py-3 bg-white shadow-sm" 
      data-testid="trading-control-bar"
      style={{ fontFamily: 'Gilroy, sans-serif' }}
    >
      <div className="flex items-center justify-between gap-4">
        {/* Left: System Status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-blue-600" />
            <span className="text-sm font-bold text-neutral-700">OPERATOR CONSOLE</span>
          </div>
          
          {systemState && (
            <div className="flex items-center gap-2 px-3 py-1 bg-neutral-50 rounded-lg border border-neutral-200">
              <div className={`w-2 h-2 rounded-full ${!isKillSwitchActive ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-xs font-semibold text-neutral-700">
                {!isKillSwitchActive ? 'SYSTEM ACTIVE' : 'SYSTEM STOPPED'}
              </span>
            </div>
          )}
        </div>
        
        {/* Right: Controls */}
        <div className="flex items-center gap-4">
          {/* System Controls */}
          <div className="flex items-center gap-2 pr-3 border-r border-neutral-200">
            {/* Kill Switch */}
            <Button
              onClick={handleKillSwitch}
              disabled={loading}
              className={`
                px-4 h-9 text-sm font-bold transition-all duration-200
                ${
                  isKillSwitchActive
                    ? 'bg-red-600 hover:bg-red-700 text-white shadow-sm'
                    : 'bg-green-600 hover:bg-green-700 text-white shadow-sm'
                }
              `}
              data-testid="kill-switch-button"
            >
              {isKillSwitchActive ? (
                <>
                  <PowerOff className="w-4 h-4 mr-2" />
                  ACTIVATE
                </>
              ) : (
                <>
                  <Power className="w-4 h-4 mr-2" />
                  STOP ALL
                </>
              )}
            </Button>
            
            {/* Mode Selector */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-neutral-600">MODE:</span>
              <Select value={currentMode} onValueChange={handleModeChange} disabled={loading}>
                <SelectTrigger 
                  className="w-[130px] h-9 bg-white border-neutral-300 text-sm font-semibold" 
                  data-testid="mode-selector"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white border-neutral-200">
                  <SelectItem value="MANUAL">MANUAL</SelectItem>
                  <SelectItem value="SEMI_AUTO">SEMI-AUTO</SelectItem>
                  <SelectItem value="AUTO">AUTO</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Sync Button */}
            <Button
              variant="outline"
              size="icon"
              onClick={handleForceSync}
              disabled={loading}
              className="h-9 w-9 bg-white border-neutral-300 hover:bg-neutral-50 hover:border-blue-400 transition-all duration-200"
              data-testid="force-sync-button"
            >
              <RefreshCw className={`w-4 h-4 text-neutral-700 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
          
          {/* Runtime Controls */}
          <div className="flex items-center gap-2">
            {/* Runtime Mode */}
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-neutral-600">RUNTIME:</span>
              <Select 
                value={runtimeMode} 
                onValueChange={handleRuntimeModeChange} 
                disabled={runtimeActions.loading}
              >
                <SelectTrigger 
                  className="w-[130px] h-9 bg-white border-neutral-300 text-sm font-semibold" 
                  data-testid="runtime-mode-selector"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white border-neutral-200">
                  <SelectItem value="MANUAL">MANUAL</SelectItem>
                  <SelectItem value="SEMI_AUTO">SEMI-AUTO</SelectItem>
                  <SelectItem value="AUTO">AUTO</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Start/Stop */}
            <Button
              onClick={isRuntimeEnabled ? handleRuntimeStop : handleRuntimeStart}
              disabled={runtimeActions.loading}
              className={`
                px-3 h-9 text-sm font-bold transition-all duration-200
                ${
                  isRuntimeEnabled
                    ? 'bg-red-600 hover:bg-red-700 text-white'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                }
              `}
              data-testid="runtime-start-stop-button"
            >
              {isRuntimeEnabled ? (
                <>
                  <Square className="w-3.5 h-3.5 mr-1.5 fill-current" />
                  STOP
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                  START
                </>
              )}
            </Button>
            
            {/* Run Once */}
            <Button
              variant="outline"
              onClick={handleRunOnce}
              disabled={runtimeActions.loading || !isRuntimeEnabled}
              className="px-3 h-9 text-sm font-bold bg-white border-neutral-300 hover:bg-blue-50 hover:border-blue-400 transition-all duration-200"
              data-testid="run-once-button"
            >
              <RotateCw className="w-3.5 h-3.5 mr-1.5" />
              RUN ONCE
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
