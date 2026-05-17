/**
 * NetworkSelector — Chain dropdown with real logos
 * Shows the active chain logo in the trigger button.
 * Dropdown expands with real chain logos + names.
 */

import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Lock } from 'lucide-react';
import { useOnchainChain, type ChainInfo } from '../context/OnchainChainContext';

const CHAIN_LOGOS: Record<string, string> = {
  eth: '/icons/chains/ethereum.png',
  arb: '/icons/chains/arbitrum.png',
  op: '/icons/chains/optimism.png',
  base: '/icons/chains/base.png',
};

export function NetworkSelector() {
  const { chainId, setChainId, chains, selectorEnabled } = useOnchainChain();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const activeChain = chains.find(c => c.chainId === chainId) || {
    chainId: 1, key: 'eth', name: 'Ethereum', enabled: true,
  };

  // Close on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const handleToggle = () => {
    if (!selectorEnabled) return;
    setOpen(!open);
  };

  const handleSelect = (chain: ChainInfo) => {
    if (!chain.enabled || !selectorEnabled) return;
    setChainId(chain.chainId);
    setOpen(false);
  };

  const iconKey = activeChain.key || 'eth';

  return (
    <div ref={ref} className="relative" data-testid="network-selector">
      <button
        onClick={handleToggle}
        disabled={!selectorEnabled}
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
          selectorEnabled
            ? 'hover:bg-gray-50 cursor-pointer'
            : 'bg-gray-50/50 cursor-default'
        }`}
        title={selectorEnabled ? activeChain.name : 'Multichain coming soon. Ethereum only.'}
        data-testid="network-selector-button"
      >
        <img
          src={CHAIN_LOGOS[iconKey] || CHAIN_LOGOS.eth}
          alt={activeChain.name}
          className="w-5 h-5 rounded-full"
        />

        {selectorEnabled ? (
          <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
        ) : (
          <Lock className="w-3 h-3 text-gray-300" />
        )}
      </button>

      {/* Dropdown */}
      {open && selectorEnabled && (
        <div className="absolute left-0 top-full mt-1 w-48 bg-white rounded-xl shadow-lg border border-gray-200 z-[9999] py-1" data-testid="network-dropdown">
          {chains.map(chain => {
            const isActive = chain.chainId === chainId;
            const ck = chain.key || 'eth';
            return (
              <button
                key={chain.chainId}
                onClick={() => handleSelect(chain)}
                disabled={!chain.enabled}
                className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-all ${
                  isActive ? 'bg-blue-50 text-blue-700' :
                  chain.enabled ? 'text-gray-700 hover:bg-gray-50' :
                  'text-gray-300 cursor-not-allowed'
                }`}
                data-testid={`network-option-${chain.key}`}
              >
                <img
                  src={CHAIN_LOGOS[ck] || CHAIN_LOGOS.eth}
                  alt={chain.name}
                  className="w-5 h-5 rounded-full"
                />
                <span>{chain.name}</span>
                {!chain.enabled && <span className="text-[10px] text-gray-300 ml-auto">soon</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
