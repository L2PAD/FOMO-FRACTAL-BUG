/**
 * OnChain Admin — Snapshot Builder Panel
 * 
 * UI for:
 * - Viewing ERC20 indexer status
 * - Triggering manual snapshots
 * - Running backfill operations
 */
import React, { useState, useEffect } from 'react';
import { Card } from './Card';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

interface ChainIndexerStatus {
  chainId: number;
  lastBlock: number;
  latestBlock: number;
  behind: number;
  totalLogs: number;
  status: 'synced' | 'syncing' | 'backfilling' | 'error';
  lastSyncAt: number;
}

interface IndexerStatus {
  ok: boolean;
  chains: ChainIndexerStatus[];
  totalLogs: number;
}

interface SnapshotResult {
  ok: boolean;
  snapshot?: {
    symbol: string;
    window: string;
    t0: number;
    state: string;
    confidence: number;
    metrics: {
      activeAddresses: number;
      txCount: number;
      transferCount: number;
      largeTransfersCount: number;
      distributionSkew: number;
      exchangeNetFlow: number;
      completeness: number;
    };
    saved: boolean;
  };
  error?: string;
}

const CHAIN_NAMES: Record<number, string> = {
  1: 'Ethereum',
  42161: 'Arbitrum',
  10: 'Optimism',
  8453: 'Base',
  137: 'Polygon',
};

const STATUS_COLORS: Record<string, string> = {
  synced: 'bg-emerald-100 text-emerald-700',
  syncing: 'bg-blue-100 text-blue-700',
  backfilling: 'bg-amber-100 text-amber-700',
  error: 'bg-red-100 text-red-700',
};

const WINDOWS = ['1h', '4h', '24h', '7d', '30d'] as const;

export function SnapshotBuilderPanel() {
  const [indexerStatus, setIndexerStatus] = useState<IndexerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Snapshot form
  const [selectedChain, setSelectedChain] = useState(1);
  const [selectedSymbol, setSelectedSymbol] = useState('ETH');
  const [selectedWindow, setSelectedWindow] = useState<typeof WINDOWS[number]>('1h');
  const [snapshotResult, setSnapshotResult] = useState<SnapshotResult | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  
  // Backfill form
  const [backfillDays, setBackfillDays] = useState(7);
  const [backfillLoading, setBackfillLoading] = useState(false);
  const [backfillMessage, setBackfillMessage] = useState<string | null>(null);

  // Load indexer status
  const loadStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const res = await fetch(`${API_BASE}/api/v10/onchain-v2/admin/indexer/status`);
      const data = await res.json();
      
      if (data.ok) {
        setIndexerStatus(data);
      } else {
        setError(data.error || 'Failed to load status');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setLoading(false);
    }
  };

  // Build snapshot
  const buildSnapshot = async () => {
    try {
      setSnapshotLoading(true);
      setSnapshotResult(null);
      
      const res = await fetch(`${API_BASE}/api/v10/onchain-v2/admin/snapshot/tick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chainId: selectedChain,
          symbol: selectedSymbol,
          window: selectedWindow,
        }),
      });
      
      const data = await res.json();
      setSnapshotResult(data);
    } catch (err) {
      setSnapshotResult({
        ok: false,
        error: err instanceof Error ? err.message : 'Network error',
      });
    } finally {
      setSnapshotLoading(false);
    }
  };

  // Run backfill
  const runBackfill = async () => {
    try {
      setBackfillLoading(true);
      setBackfillMessage(null);
      
      const res = await fetch(`${API_BASE}/api/v10/onchain-v2/admin/snapshot/backfill-metrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chainId: selectedChain,
          symbol: selectedSymbol,
          window: selectedWindow,
          days: backfillDays,
        }),
      });
      
      const data = await res.json();
      
      if (data.ok) {
        setBackfillMessage(data.message);
      } else {
        setBackfillMessage(`Error: ${data.error}`);
      }
    } catch (err) {
      setBackfillMessage(`Error: ${err instanceof Error ? err.message : 'Network error'}`);
    } finally {
      setBackfillLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    
    // Auto-refresh every 30s
    const interval = setInterval(loadStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatNumber = (n: number) => n.toLocaleString();
  const formatTime = (ts: number) => new Date(ts).toLocaleTimeString();

  return (
    <Card title="Snapshot Builder & Indexer" data-testid="snapshot-builder-panel">
      {/* Indexer Status */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-700">ERC20 Indexer Status</h3>
          <button
            onClick={loadStatus}
            disabled={loading}
            className="px-3 py-1 text-xs bg-slate-100 hover:bg-slate-200 rounded-lg disabled:opacity-50"
            data-testid="refresh-indexer-btn"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        </div>

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mb-3">
            {error}
          </div>
        )}

        {indexerStatus && (
          <div className="space-y-2">
            {/* Summary */}
            <div className="p-3 bg-slate-50 rounded-lg flex items-center justify-between">
              <div className="text-sm">
                <span className="text-slate-500">Total Indexed Logs:</span>{' '}
                <span className="font-bold text-slate-800">{formatNumber(indexerStatus.totalLogs)}</span>
              </div>
              <div className="text-sm">
                <span className="text-slate-500">Chains:</span>{' '}
                <span className="font-medium">{indexerStatus.chains.length}</span>
              </div>
            </div>

            {/* Per-chain status */}
            {indexerStatus.chains.map(chain => (
              <div
                key={chain.chainId}
                className="p-3 bg-white border border-slate-200 rounded-lg"
                data-testid={`chain-status-${chain.chainId}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-medium text-slate-700">
                      {CHAIN_NAMES[chain.chainId] || `Chain ${chain.chainId}`}
                    </span>
                    <span className={`px-2 py-0.5 text-xs font-medium rounded ${STATUS_COLORS[chain.status]}`}>
                      {chain.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500">
                    Last sync: {formatTime(chain.lastSyncAt)}
                  </div>
                </div>
                
                <div className="mt-2 grid grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="text-slate-500">Logs:</span>{' '}
                    <span className="font-medium">{formatNumber(chain.totalLogs)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Last Block:</span>{' '}
                    <span className="font-mono">{formatNumber(chain.lastBlock)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Latest:</span>{' '}
                    <span className="font-mono">{formatNumber(chain.latestBlock)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">Behind:</span>{' '}
                    <span className={`font-medium ${chain.behind > 1000 ? 'text-amber-600' : 'text-emerald-600'}`}>
                      {formatNumber(chain.behind)} blocks
                    </span>
                  </div>
                </div>
                
                {/* Progress bar */}
                {chain.latestBlock > 0 && (
                  <div className="mt-2">
                    <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 transition-all"
                        style={{
                          width: `${Math.min(100, (chain.lastBlock / chain.latestBlock) * 100)}%`,
                        }}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-slate-200 my-6" />

      {/* Snapshot Builder */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Build Snapshot from Indexed Data</h3>
        
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          {/* Form */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            <div>
              <label className="text-xs text-slate-600 block mb-1">Chain</label>
              <select
                value={selectedChain}
                onChange={e => setSelectedChain(Number(e.target.value))}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white"
                data-testid="chain-select"
              >
                {Object.entries(CHAIN_NAMES).map(([id, name]) => (
                  <option key={id} value={id}>{name}</option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="text-xs text-slate-600 block mb-1">Symbol</label>
              <input
                type="text"
                value={selectedSymbol}
                onChange={e => setSelectedSymbol(e.target.value.toUpperCase())}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                placeholder="ETH"
                data-testid="symbol-input"
              />
            </div>
            
            <div>
              <label className="text-xs text-slate-600 block mb-1">Window</label>
              <select
                value={selectedWindow}
                onChange={e => setSelectedWindow(e.target.value as typeof WINDOWS[number])}
                className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white"
                data-testid="window-select"
              >
                {WINDOWS.map(w => (
                  <option key={w} value={w}>{w}</option>
                ))}
              </select>
            </div>
            
            <div className="flex items-end">
              <button
                onClick={buildSnapshot}
                disabled={snapshotLoading || !selectedSymbol}
                className="w-full px-4 py-2 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg disabled:opacity-50"
                data-testid="build-snapshot-btn"
              >
                {snapshotLoading ? 'Building...' : 'Build Snapshot'}
              </button>
            </div>
          </div>

          {/* Result */}
          {snapshotResult && (
            <div className={`p-3 rounded-lg ${snapshotResult.ok ? 'bg-white border border-emerald-200' : 'bg-red-100 border border-red-300'}`}>
              {snapshotResult.ok && snapshotResult.snapshot ? (
                <div data-testid="snapshot-result">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-800">{snapshotResult.snapshot.symbol}</span>
                      <span className="text-xs text-slate-500">{snapshotResult.snapshot.window}</span>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                        snapshotResult.snapshot.state === 'ACCUMULATION' ? 'bg-emerald-100 text-emerald-700' :
                        snapshotResult.snapshot.state === 'DISTRIBUTION' ? 'bg-red-100 text-red-700' :
                        snapshotResult.snapshot.state === 'NEUTRAL' ? 'bg-slate-100 text-slate-700' :
                        'bg-yellow-100 text-yellow-700'
                      }`}>
                        {snapshotResult.snapshot.state}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500">
                      Confidence: {(snapshotResult.snapshot.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  
                  <div className="grid grid-cols-4 gap-3 text-xs">
                    <div className="bg-slate-50 p-2 rounded">
                      <div className="text-slate-500">Active Addresses</div>
                      <div className="font-bold text-slate-800">{formatNumber(snapshotResult.snapshot.metrics.activeAddresses)}</div>
                    </div>
                    <div className="bg-slate-50 p-2 rounded">
                      <div className="text-slate-500">Transactions</div>
                      <div className="font-bold text-slate-800">{formatNumber(snapshotResult.snapshot.metrics.txCount)}</div>
                    </div>
                    <div className="bg-slate-50 p-2 rounded">
                      <div className="text-slate-500">Transfers</div>
                      <div className="font-bold text-slate-800">{formatNumber(snapshotResult.snapshot.metrics.transferCount)}</div>
                    </div>
                    <div className="bg-slate-50 p-2 rounded">
                      <div className="text-slate-500">Whale Transfers</div>
                      <div className="font-bold text-slate-800">{formatNumber(snapshotResult.snapshot.metrics.largeTransfersCount)}</div>
                    </div>
                  </div>
                  
                  {snapshotResult.snapshot.saved && (
                    <div className="mt-2 text-xs text-emerald-600">✓ Saved to database</div>
                  )}
                </div>
              ) : (
                <div className="text-sm text-red-700" data-testid="snapshot-error">
                  Error: {snapshotResult.error}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Divider */}
      <div className="border-t border-slate-200 my-6" />

      {/* Backfill Metrics */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Backfill Historical Metrics</h3>
        
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-xs text-amber-700 mb-3">
            Generate historical snapshots from indexed logs. Runs in background.
          </p>
          
          <div className="flex items-end gap-3">
            <div>
              <label className="text-xs text-slate-600 block mb-1">Days to Backfill</label>
              <input
                type="number"
                value={backfillDays}
                onChange={e => setBackfillDays(Math.max(1, Math.min(30, Number(e.target.value))))}
                min={1}
                max={30}
                className="w-24 px-3 py-2 text-sm border border-slate-200 rounded-lg"
                data-testid="backfill-days-input"
              />
            </div>
            
            <button
              onClick={runBackfill}
              disabled={backfillLoading}
              className="px-4 py-2 text-sm bg-amber-600 hover:bg-amber-700 text-white rounded-lg disabled:opacity-50"
              data-testid="run-backfill-btn"
            >
              {backfillLoading ? 'Starting...' : `Backfill ${selectedSymbol} ${selectedWindow}`}
            </button>
          </div>
          
          {backfillMessage && (
            <div className={`mt-3 p-2 rounded text-xs ${
              backfillMessage.startsWith('Error') ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
            }`}>
              {backfillMessage}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
