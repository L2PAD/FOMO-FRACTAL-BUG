/**
 * RenderPlanOverlay V2
 * ====================
 * 
 * Master component that renders all layers of render_plan v2.
 * 
 * LAYERS:
 * A. Market State (trend, channel, volatility - as CONTEXT, not pattern)
 * B. Structure (swings, CHOCH, BOS)
 * C. Indicators (overlays, panes)
 * D. Pattern Figures (ONLY real patterns from registry - NO CHANNELS)
 * E. Liquidity (EQH/EQL, sweeps, OB)
 * F. Execution (ALWAYS visible: valid/waiting/no_trade)
 * 
 * NO TRADE: Single unified indicator on LEFT (via NoTradeIndicator)
 * - Replaces multiple "NO TRADE" badges
 * 
 * Key principle: 1 graph = 1 setup = 1 story
 */

import React from 'react';
import { MarketStateRenderer } from './MarketStateRenderer';
import { ExecutionRenderer } from './ExecutionRenderer';
import { PatternRenderer } from './PatternRenderer';
import { POIRenderer } from './POIRenderer';
import { StructureRenderer } from './StructureRenderer';
import { LiquidityRenderer } from './LiquidityRenderer';
import { RangeContextRenderer } from './RangeContextRenderer';
import { ChainHighlightRenderer } from './ChainHighlightRenderer';
import { NoTradeIndicator } from './NoTradeIndicator';

export const RenderPlanOverlay = ({ renderPlan, onChainStepClick }) => {
  if (!renderPlan) return null;

  const {
    market_state,
    structure,
    indicators,
    patterns,
    liquidity,
    execution,
    poi,
    meta,
    range_context,
    render_mode,
    chain_highlight,
  } = renderPlan;
  
  // Check render mode
  const isRangeMode = render_mode === 'range_mode' || meta?.render_mode === 'range_mode';
  
  // Determine if we have a valid setup
  const hasValidExecution = execution?.status === 'valid';
  const hasValidPattern = patterns?.has_figure && patterns?.primary;
  const isNoTrade = !hasValidExecution && !hasValidPattern;
  
  // Build NO TRADE reason
  let noTradeReason = '';
  if (isNoTrade) {
    if (execution?.reason) {
      noTradeReason = execution.reason;
    } else if (!patterns?.has_figure) {
      noTradeReason = patterns?.reason || 'No active figure detected';
    } else {
      noTradeReason = 'Setup conditions not met';
    }
  }

  return (
    <>
      {/* Layer A: Market State (context badge, NOT pattern) */}
      <MarketStateRenderer marketState={market_state} />
      
      {/* UNIFIED NO TRADE indicator — LEFT side, single instance */}
      {isNoTrade && (
        <NoTradeIndicator 
          isVisible={true}
          reason={noTradeReason}
        />
      )}
      
      {/* Layer F: Execution — ONLY if valid (hide NO TRADE since we show it above) */}
      {hasValidExecution && (
        <ExecutionRenderer execution={execution} />
      )}
      
      {/* Range Context (for range_mode - shows boundaries, triggers) */}
      {isRangeMode && range_context && (
        <RangeContextRenderer 
          rangeContext={range_context}
          marketState={market_state}
        />
      )}
      
      {/* Layer D: Pattern — ONLY if has_figure (no "No active figure" badge) */}
      {!isRangeMode && hasValidPattern && patterns?.primary && (
        <PatternRenderer pattern={patterns.primary} />
      )}
      
      {/* POI - closest zone only */}
      <POIRenderer zones={poi} />
      
      {/* Layer B: Structure - simplified */}
      <StructureRenderer structure={structure} />
      
      {/* Layer E: Liquidity - limited */}
      <LiquidityRenderer liquidity={liquidity} />
      
      {/* Chain Highlight - visual storytelling (if available) */}
      {chain_highlight && chain_highlight.length > 0 && (
        <ChainHighlightRenderer 
          chain={chain_highlight} 
          onStepClick={onChainStepClick}
        />
      )}
    </>
  );
};

export default RenderPlanOverlay;
