/**
 * Cognitive Trading Terminal - Complete integrated view
 * ===================================================
 * 
 * Combines:
 * - Chart Intelligence Layer (execution zones, structure overlays)
 * - Analysis Stack (Entry Timing, Microstructure, Validation panels)
 * - Operations Tabs (Positions, Orders, Trades)
 * - Binding Layer (bidirectional hover/click connection)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Target, Wifi, WifiOff, Clock } from 'lucide-react';
import TradingChart from '../components/charts/TradingChart';
import { BindingProvider } from '../components/terminal/binding/BindingProvider';
import AnalysisStack from '../components/terminal/analysis/AnalysisStack';
import OperationsTabs from '../components/terminal/operations/OperationsTabs';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const TIMEFRAMES = ['1H', '4H', '1D'];

const fetchTerminalState = async (symbol, timeframe) => {
  const res = await fetch(`${API_URL}/api/terminal/state/${symbol}?timeframe=${timeframe}`);
  if (!res.ok) throw new Error(`Failed to fetch: ${res.status}`);
  return res.json();
};

export default function CognitiveTerminalPage() {
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('4H');
  const [state, setState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);

  const loadState = useCallback(async () => {
    try {
      const response = await fetchTerminalState(symbol, timeframe);
      if (response.ok && response.data) {
        setState(response.data);
        setLastUpdate(new Date());
        setConnected(true);
      }
    } catch (error) {
      console.error('Terminal state error:', error);
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => {
    loadState();
    const interval = setInterval(() => loadState(), 3000);
    return () => clearInterval(interval);
  }, [loadState]);

  if (loading && !state) {
    return (
      <div className="flex h-screen w-full bg-[#0A0E14] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-gray-700 border-t-white rounded-full animate-spin" />
          <p className="text-sm text-gray-500">Loading Cognitive Terminal...</p>
        </div>
      </div>
    );
  }

  const execution = state?.execution || {};
  const decision = state?.decision || {};

  return (
    <BindingProvider>
      <div className="flex h-screen w-full bg-[#0A0E14] overflow-hidden font-sans text-white">
        {/* Sidebar */}
        <aside className="h-full w-16 lg:w-64 bg-[#0F141A] border-r border-white/10 flex-shrink-0 flex flex-col">
          {/* Logo */}
          <div className="h-14 flex items-center justify-center lg:justify-start lg:px-4 border-b border-white/10">
            <Target className="w-6 h-6 text-blue-500" />
            <span className="hidden lg:block ml-2 text-white font-bold text-sm tracking-widest uppercase">
              Cognitive Terminal
            </span>
          </div>

          {/* Symbol Selector */}
          <div className="p-2 lg:p-4 border-b border-white/10">
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full bg-[#11161D] text-white text-sm font-medium px-3 py-2 rounded border border-white/10 focus:border-blue-500 outline-none"
            >
              <option value="BTCUSDT">BTC/USDT</option>
              <option value="ETHUSDT">ETH/USDT</option>
              <option value="SOLUSDT">SOL/USDT</option>
            </select>
          </div>

          {/* Timeframe Selector */}
          <div className="p-2 lg:p-4 border-b border-white/10">
            <div className="hidden lg:flex items-center gap-1 mb-2">
              <Clock className="w-3 h-3 text-gray-500" />
              <span className="text-xs text-gray-500 uppercase tracking-wider">Timeframe</span>
            </div>
            <div className="flex gap-1">
              {TIMEFRAMES.map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`flex-1 px-2 py-1.5 text-xs font-bold rounded transition-all ${
                    timeframe === tf
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                      : 'bg-[#11161D] text-gray-400 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Connection Status */}
          <div className="mt-auto p-4 border-t border-white/10">
            <div className={`flex items-center gap-2 text-xs ${connected ? 'text-green-400' : 'text-red-400'}`}>
              {connected ? <Wifi className="w-4 h-4" /> : <WifiOff className="w-4 h-4" />}
              <span className="hidden lg:block font-medium">
                {connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            {lastUpdate && (
              <div className="mt-1 text-xs text-gray-500 hidden lg:block">
                {lastUpdate.toLocaleTimeString()}
              </div>
            )}
          </div>
        </aside>

        {/* Main Area */}
        <div className="flex-1 flex flex-col h-full overflow-hidden">
          {/* Top Bar */}
          <header className="h-14 border-b border-white/10 bg-[#0F141A] flex items-center justify-between px-6 flex-shrink-0">
            <div className="flex items-center gap-4">
              <h1 className="text-sm font-bold uppercase tracking-widest text-white">
                {symbol}
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-blue-600 text-white font-bold">
                {timeframe}
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  state?.system?.mode === 'LIVE'
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                }`}
              >
                {state?.system?.mode === 'LIVE' ? 'LIVE' : 'SIMULATION'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={loadState}
                className="p-2 hover:bg-white/5 rounded transition-colors"
              >
                <RefreshCw className="w-4 h-4 text-gray-400 hover:text-white" />
              </button>
            </div>
          </header>

          {/* Content Grid */}
          <main className="flex-1 overflow-auto p-4 md:p-6 space-y-6">
            {/* Chart Section */}
            <div className="rounded-xl border border-white/10 bg-[#0F141A] overflow-hidden">
              <TradingChart
                symbol={symbol}
                timeframe={timeframe}
                execution={execution}
                decision={decision}
                structure={state?.structure || null}
                height={500}
                showVolume={true}
              />
            </div>

            {/* Analysis Stack */}
            <AnalysisStack 
              data={state} 
              symbol={symbol} 
              timeframe={timeframe} 
            />

            {/* Operations Tabs */}
            <OperationsTabs
              data={{
                positions: state?.positions_preview || [],
                orders: state?.orders_preview || [],
                trades: state?.trades_preview || [],
              }}
              symbol={symbol}
              timeframe={timeframe}
            />
          </main>
        </div>
      </div>
    </BindingProvider>
  );
}
