/**
 * OnChain Admin — RPC Pool Panel
 * 
 * UI for managing RPC endpoints (Infura, Alchemy, etc.)
 */
import React, { useState, useEffect } from 'react';
import { Card } from './Card';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

interface RpcEndpoint {
  id: string;
  url: string;
  provider: string;
  chainId: number;
  chainName: string;
  enabled: boolean;
  weight: number;
}

interface RpcHealth {
  id: string;
  healthy: boolean;
  latencyMs: number;
  lastError?: string;
}

interface RpcConfig {
  version: number;
  updatedAt: number;
  updatedBy: string;
  endpoints: RpcEndpoint[];
}

interface RpcPoolState {
  config: RpcConfig | null;
  health: {
    healthyCount: number;
    totalCount: number;
    avgLatencyMs: number;
    endpoints: RpcHealth[];
  } | null;
  loading: boolean;
  testing: boolean;
  error: string | null;
}

// All chains supported by Infura
const INFURA_CHAINS: Array<{ id: number; name: string; slug: string }> = [
  { id: 1, name: 'Ethereum Mainnet', slug: 'mainnet' },
  { id: 11155111, name: 'Ethereum Sepolia', slug: 'sepolia' },
  { id: 42161, name: 'Arbitrum One', slug: 'arbitrum-mainnet' },
  { id: 421614, name: 'Arbitrum Sepolia', slug: 'arbitrum-sepolia' },
  { id: 10, name: 'Optimism', slug: 'optimism-mainnet' },
  { id: 11155420, name: 'Optimism Sepolia', slug: 'optimism-sepolia' },
  { id: 137, name: 'Polygon', slug: 'polygon-mainnet' },
  { id: 80002, name: 'Polygon Amoy', slug: 'polygon-amoy' },
  { id: 8453, name: 'Base', slug: 'base-mainnet' },
  { id: 84532, name: 'Base Sepolia', slug: 'base-sepolia' },
  { id: 59144, name: 'Linea', slug: 'linea-mainnet' },
  { id: 59141, name: 'Linea Sepolia', slug: 'linea-sepolia' },
  { id: 56, name: 'BNB Chain', slug: 'bsc-mainnet' },
  { id: 43114, name: 'Avalanche C-Chain', slug: 'avalanche-mainnet' },
  { id: 250, name: 'Fantom', slug: 'fantom-mainnet' },
  { id: 324, name: 'zkSync Era', slug: 'zksync-mainnet' },
];

// Alchemy chains
const ALCHEMY_CHAINS: Array<{ id: number; name: string; slug: string }> = [
  { id: 1, name: 'Ethereum Mainnet', slug: 'eth-mainnet' },
  { id: 11155111, name: 'Ethereum Sepolia', slug: 'eth-sepolia' },
  { id: 42161, name: 'Arbitrum One', slug: 'arb-mainnet' },
  { id: 10, name: 'Optimism', slug: 'opt-mainnet' },
  { id: 137, name: 'Polygon', slug: 'polygon-mainnet' },
  { id: 8453, name: 'Base', slug: 'base-mainnet' },
];

const CHAIN_NAMES: Record<number, string> = {
  1: 'Ethereum',
  42161: 'Arbitrum',
  10: 'Optimism',
  8453: 'Base',
  137: 'Polygon',
  56: 'BNB',
  43114: 'Avalanche',
  250: 'Fantom',
  324: 'zkSync',
  59144: 'Linea',
};

const PROVIDER_COLORS: Record<string, string> = {
  infura: 'bg-orange-100 text-orange-700',
  alchemy: 'bg-blue-100 text-blue-700',
  ankr: 'bg-purple-100 text-purple-700',
  llama: 'bg-green-100 text-green-700',
  quicknode: 'bg-pink-100 text-pink-700',
  custom: 'bg-slate-100 text-slate-700',
};

export function RpcPoolPanel() {
  const [state, setState] = useState<RpcPoolState>({
    config: null,
    health: null,
    loading: true,
    testing: false,
    error: null,
  });
  
  const [showAddForm, setShowAddForm] = useState(false);
  const [addMode, setAddMode] = useState<'infura' | 'alchemy' | 'custom'>('infura');
  const [apiKey, setApiKey] = useState('');
  const [selectedChains, setSelectedChains] = useState<number[]>([1]); // Default ETH
  const [customUrl, setCustomUrl] = useState('');
  const [customChainId, setCustomChainId] = useState(1);

  // Build URL from API key
  const buildInfuraUrl = (chainSlug: string, key: string) => 
    `https://${chainSlug}.infura.io/v3/${key}`;
  
  const buildAlchemyUrl = (chainSlug: string, key: string) =>
    `https://${chainSlug}.g.alchemy.com/v2/${key}`;

  // Load config
  const loadConfig = async () => {
    try {
      setState(s => ({ ...s, loading: true, error: null }));
      const res = await fetch(`${API_BASE}/api/v10/onchain-v2/admin/rpc`);
      const data = await res.json();
      
      if (data.ok) {
        setState(s => ({
          ...s,
          config: data.config,
          health: data.health,
          loading: false,
        }));
      } else {
        setState(s => ({ ...s, error: data.error || 'Failed to load', loading: false }));
      }
    } catch (err) {
      setState(s => ({ 
        ...s, 
        error: err instanceof Error ? err.message : 'Network error', 
        loading: false 
      }));
    }
  };

  // Test all endpoints
  const testEndpoints = async () => {
    try {
      setState(s => ({ ...s, testing: true }));
      const res = await fetch(`${API_BASE}/api/v10/onchain-v2/admin/rpc/test`, {
        method: 'POST',
      });
      const data = await res.json();
      
      if (data.ok) {
        setState(s => ({
          ...s,
          health: {
            ...s.health!,
            endpoints: data.results,
            healthyCount: data.summary.healthyCount,
            totalCount: data.summary.totalCount,
            avgLatencyMs: data.summary.avgLatencyMs,
          },
          testing: false,
        }));
      }
    } catch {
      // Ignore
    } finally {
      setState(s => ({ ...s, testing: false }));
    }
  };

  // Add endpoints (Infura/Alchemy with multiple chains)
  const addEndpoints = async () => {
    if (addMode === 'custom') {
      if (!customUrl) return;
      await addSingleEndpoint({
        url: customUrl,
        chainId: customChainId,
        provider: 'custom',
      });
    } else {
      if (!apiKey) return;
      
      const chains = addMode === 'infura' ? INFURA_CHAINS : ALCHEMY_CHAINS;
      const buildUrl = addMode === 'infura' ? buildInfuraUrl : buildAlchemyUrl;
      
      for (const chainId of selectedChains) {
        const chain = chains.find(c => c.id === chainId);
        if (!chain) continue;
        
        const url = buildUrl(chain.slug, apiKey);
        await addSingleEndpoint({
          url,
          chainId: chain.id,
          provider: addMode,
        });
      }
    }
    
    setShowAddForm(false);
    setApiKey('');
    setSelectedChains([1]);
    setCustomUrl('');
    loadConfig();
  };

  // Add single endpoint
  const addSingleEndpoint = async (ep: { url: string; chainId: number; provider: string }) => {
    const id = `${CHAIN_NAMES[ep.chainId]?.toLowerCase() || 'chain'}-${ep.provider}-${Date.now()}`;
    
    try {
      await fetch(`${API_BASE}/api/v10/onchain-v2/admin/rpc/endpoint`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id,
          url: ep.url,
          chainId: ep.chainId,
          chainName: CHAIN_NAMES[ep.chainId]?.toLowerCase() || 'unknown',
          provider: ep.provider,
          enabled: true,
          weight: 5,
        }),
      });
    } catch {
      // Continue with other chains
    }
  };

  // Remove endpoint
  const removeEndpoint = async (id: string) => {
    if (!confirm(`Remove endpoint ${id}?`)) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/v10/onchain-v2/admin/rpc/endpoint/${id}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      
      if (data.ok) {
        loadConfig();
      } else {
        alert(data.error || 'Failed to remove');
      }
    } catch {
      alert('Network error');
    }
  };

  // Toggle chain selection
  const toggleChain = (chainId: number) => {
    setSelectedChains(prev => 
      prev.includes(chainId) 
        ? prev.filter(c => c !== chainId)
        : [...prev, chainId]
    );
  };

  // Select all mainnets
  const selectAllMainnets = () => {
    const chains = addMode === 'infura' ? INFURA_CHAINS : ALCHEMY_CHAINS;
    const mainnets = chains.filter(c => !c.name.includes('Sepolia') && !c.name.includes('Amoy')).map(c => c.id);
    setSelectedChains(mainnets);
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const endpoints = state.config?.endpoints || [];
  const healthMap = new Map(state.health?.endpoints?.map(h => [h.id, h]) || []);
  const availableChains = addMode === 'infura' ? INFURA_CHAINS : ALCHEMY_CHAINS;

  return (
    <Card title="RPC Pool Configuration">
      {/* Status Bar */}
      <div className="flex items-center justify-between mb-4 p-3 bg-slate-50 rounded-lg">
        <div className="flex items-center gap-4">
          <div className="text-sm">
            <span className="text-slate-500">Endpoints:</span>{' '}
            <span className="font-medium">
              {state.health?.healthyCount || 0}/{state.health?.totalCount || 0} healthy
            </span>
          </div>
          <div className="text-sm">
            <span className="text-slate-500">Avg Latency:</span>{' '}
            <span className="font-medium">{state.health?.avgLatencyMs || 0}ms</span>
          </div>
          <div className="text-sm">
            <span className="text-slate-500">Version:</span>{' '}
            <span className="font-medium">v{state.config?.version || 0}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={testEndpoints}
            disabled={state.testing}
            className="px-3 py-1.5 text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg disabled:opacity-50"
          >
            {state.testing ? 'Testing...' : 'Test All'}
          </button>
          <button
            onClick={() => setShowAddForm(true)}
            className="px-3 py-1.5 text-xs bg-emerald-50 hover:bg-emerald-100 text-emerald-700 rounded-lg"
          >
            + Add RPC
          </button>
        </div>
      </div>

      {/* Add Form */}
      {showAddForm && (
        <div className="mb-4 p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-emerald-800">Add RPC Endpoints</div>
            <div className="flex gap-1">
              {(['infura', 'alchemy', 'custom'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => setAddMode(mode)}
                  className={`px-3 py-1 text-xs rounded-lg ${
                    addMode === mode 
                      ? 'bg-emerald-600 text-white' 
                      : 'bg-white text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {addMode !== 'custom' ? (
            <>
              {/* API Key Input */}
              <div className="mb-3">
                <label className="text-xs text-slate-600 block mb-1">
                  {addMode === 'infura' ? 'Infura' : 'Alchemy'} API Key
                </label>
                <input
                  type="text"
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder={addMode === 'infura' ? 'b11a22f4a07b43aca5252a086a7685f6' : 'your-alchemy-key'}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 font-mono"
                />
              </div>

              {/* Chain Selection */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs text-slate-600">Select Chains</label>
                  <button
                    onClick={selectAllMainnets}
                    className="text-xs text-emerald-600 hover:underline"
                  >
                    Select All Mainnets
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto p-2 bg-white rounded-lg border border-slate-200">
                  {availableChains.map(chain => (
                    <label 
                      key={chain.id} 
                      className={`flex items-center gap-2 p-2 rounded cursor-pointer text-xs ${
                        selectedChains.includes(chain.id) ? 'bg-emerald-100' : 'hover:bg-slate-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedChains.includes(chain.id)}
                        onChange={() => toggleChain(chain.id)}
                        className="rounded text-emerald-600"
                      />
                      <span className={chain.name.includes('Sepolia') || chain.name.includes('Amoy') ? 'text-slate-400' : ''}>
                        {chain.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            </>
          ) : (
            /* Custom URL */
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="col-span-2">
                <label className="text-xs text-slate-600 block mb-1">Full RPC URL</label>
                <input
                  type="text"
                  value={customUrl}
                  onChange={e => setCustomUrl(e.target.value)}
                  placeholder="https://your-rpc-url.com/..."
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                />
              </div>
              <div>
                <label className="text-xs text-slate-600 block mb-1">Chain ID</label>
                <input
                  type="number"
                  value={customChainId}
                  onChange={e => setCustomChainId(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg"
                />
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={addEndpoints}
              disabled={addMode === 'custom' ? !customUrl : !apiKey || selectedChains.length === 0}
              className="px-4 py-2 text-sm bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg disabled:opacity-50"
            >
              {addMode !== 'custom' && selectedChains.length > 1 
                ? `Add ${selectedChains.length} Endpoints` 
                : 'Add Endpoint'}
            </button>
            <button
              onClick={() => setShowAddForm(false)}
              className="px-4 py-2 text-sm bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Loading */}
      {state.loading && (
        <div className="text-center py-8 text-slate-500">Loading...</div>
      )}

      {/* Error */}
      {state.error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 mb-4">
          {state.error}
        </div>
      )}

      {/* Endpoints List */}
      {!state.loading && endpoints.length === 0 && (
        <div className="text-center py-8 text-slate-400 text-sm">
          No RPC endpoints configured. Click "+ Add RPC" to add Infura or Alchemy.
        </div>
      )}

      {!state.loading && endpoints.length > 0 && (
        <div className="space-y-2">
          {endpoints.map(ep => {
            const health = healthMap.get(ep.id);
            const isHealthy = health?.healthy !== false;
            
            return (
              <div
                key={ep.id}
                className={`p-3 rounded-lg border ${
                  isHealthy ? 'bg-white border-slate-200' : 'bg-red-50 border-red-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {/* Health indicator */}
                    <div className={`w-2 h-2 rounded-full ${isHealthy ? 'bg-emerald-500' : 'bg-red-500'}`} />
                    
                    {/* Provider badge */}
                    <span className={`px-2 py-0.5 text-xs font-medium rounded ${PROVIDER_COLORS[ep.provider] || PROVIDER_COLORS.custom}`}>
                      {ep.provider.toUpperCase()}
                    </span>
                    
                    {/* Chain */}
                    <span className="text-sm font-medium text-slate-700">
                      {CHAIN_NAMES[ep.chainId] || `Chain ${ep.chainId}`}
                    </span>
                    
                    {/* URL (masked) */}
                    <span className="text-xs text-slate-400 font-mono truncate max-w-[200px]">
                      {ep.url?.substring(0, 40)}...
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-3">
                    {/* Latency */}
                    {health?.latencyMs !== undefined && health.latencyMs > 0 && (
                      <span className="text-xs text-slate-500">
                        {health.latencyMs}ms
                      </span>
                    )}
                    
                    {/* Error */}
                    {health?.lastError && (
                      <span className="text-xs text-red-500 truncate max-w-[150px]" title={health.lastError}>
                        {health.lastError}
                      </span>
                    )}
                    
                    {/* Weight */}
                    <span className="text-xs text-slate-400">
                      w:{ep.weight}
                    </span>
                    
                    {/* Enabled */}
                    <span className={`text-xs ${ep.enabled ? 'text-emerald-600' : 'text-slate-400'}`}>
                      {ep.enabled ? 'ON' : 'OFF'}
                    </span>
                    
                    {/* Remove */}
                    <button
                      onClick={() => removeEndpoint(ep.id)}
                      className="text-red-400 hover:text-red-600 text-sm"
                      title="Remove"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
