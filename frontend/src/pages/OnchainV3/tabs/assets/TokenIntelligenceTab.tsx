/**
 * Token Intelligence Tab — v3 (Decision Terminal)
 * =================================================
 * Layout:
 *   Trading Decision Banner (dark, full width)
 *   Market Narrative (dark, full width)
 *   Row 1: Signals (dark) | Flow Map (light, expanded)
 *   Row 2: Token Score (dark) | Market Pressure (dark) | Regime (light)
 *   Row 3: Smart Timing (dark) | Liquidity Absorption (light) | Positioning (light)
 *   Row 4: Wallet Activity (light) | Trending Tokens (dark)
 */

import React, { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useOnchainChain } from '../../context/OnchainChainContext';
import { useTokenIntelligence } from './hooks/useTokenIntelligence';
import { TradingDecisionBanner } from './components/TokenNarrative';
import { MarketNarrative } from './components/MarketNarrative';
import { TokenSignals } from './components/TokenSignals';
import { TrendingTokens } from './components/TrendingTokens';
import { TokenFlowHeat } from './components/TokenFlowHeat';
import { WalletActivity } from './components/WalletActivity';
import { TokenPositioning } from './components/TokenPositioning';
import { SmartTokenScore } from './components/SmartTokenScore';
import { MarketPressure } from './components/MarketPressure';
import { TokenRegime } from './components/TokenRegime';
import { SmartTiming } from './components/SmartTiming';
import { LiquidityAbsorption } from './components/LiquidityAbsorption';
import { TokenProfilePage } from './TokenProfilePage';

type WindowKey = '24h' | '7d' | '30d';

interface TokenIntelligenceProps {
  onNavigateTab?: (tab: string, params?: Record<string, string>) => void;
}

export function TokenIntelligenceTab({ onNavigateTab }: TokenIntelligenceProps) {
  const { chainId } = useOnchainChain();
  const [window, setWindow] = useState<WindowKey>('7d');
  const [selectedToken, setSelectedToken] = useState<string | null>(null);
  const data = useTokenIntelligence(chainId, window);

  const handleSelectToken = (symbol: string) => {
    setSelectedToken(symbol);
  };

  if (selectedToken) {
    return (
      <TokenProfilePage
        symbol={selectedToken}
        onBack={() => setSelectedToken(null)}
        onSelectToken={handleSelectToken}
      />
    );
  }

  return (
    <div className="space-y-4" data-testid="token-intelligence-tab">
      {/* Header: window + refresh */}
      <div className="flex items-center justify-end gap-3" data-testid="token-intel-header">
        <div className="flex items-center gap-1" data-testid="token-intel-window">
          {(['24h', '7d', '30d'] as WindowKey[]).map((w) => (
            <button key={w} onClick={() => setWindow(w)}
              className={`px-3 py-1.5 text-xs font-bold transition-colors ${
                window === w ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'
              }`} data-testid={`token-intel-window-${w}`}>
              {w.toUpperCase()}
            </button>
          ))}
        </div>
        <button onClick={data.refresh} disabled={data.loading}
          className="p-2 text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50"
          data-testid="token-intel-refresh">
          <RefreshCw className={`w-4 h-4 ${data.loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Trading Decision Banner — full width, dark */}
      <TradingDecisionBanner
        narrative={data.narrative}
        scores={data.tokenScores}
        patterns={data.patterns}
        heat={data.destinationHeat}
        loading={data.loading}
      />

      {/* Market Narrative — full width, dark */}
      <MarketNarrative
        narrative={data.narrative}
        scores={data.tokenScores}
        patterns={data.patterns}
        heat={data.destinationHeat}
        loading={data.loading}
      />

      {/* Row 1: Signals (dark, 2fr) + Flow Map (light, 3fr) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2">
          <TokenSignals signals={data.signals} scores={data.tokenScores} loading={data.loading} />
        </div>
        <div className="lg:col-span-3">
          <TokenFlowHeat heat={data.destinationHeat} patterns={data.patterns} loading={data.loading} onSelectToken={handleSelectToken} />
        </div>
      </div>

      {/* Row 2: Token Score (dark) | Market Pressure (dark) | Regime (light) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SmartTokenScore scores={data.tokenScores} loading={data.loading} onSelectToken={handleSelectToken} />
        <MarketPressure scores={data.tokenScores} loading={data.loading} />
        <TokenRegime scores={data.tokenScores} patterns={data.patterns} narrative={data.narrative} loading={data.loading} />
      </div>

      {/* Row 3: Timing (dark) + Liquidity (light) + Positioning (light) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SmartTiming scores={data.tokenScores} loading={data.loading} />
        <LiquidityAbsorption scores={data.tokenScores} heat={data.destinationHeat} loading={data.loading} />
        <TokenPositioning scores={data.tokenScores} patterns={data.patterns} loading={data.loading} />
      </div>

      {/* Row 4: Wallet Activity (light) + Trending (dark) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <WalletActivity actors={data.actors} loading={data.loading} />
        <TrendingTokens scores={data.tokenScores} loading={data.loading} onSelectToken={handleSelectToken} />
      </div>
    </div>
  );
}

export default TokenIntelligenceTab;
