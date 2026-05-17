/**
 * OnChain V2 — DEX VWAP Price Source
 * ====================================
 * 
 * STEP 1: USD Valuation Layer
 * Fallback source: calculates price from recent DEX swaps.
 * Low confidence source (0.35) — derived from our own indexed data.
 */

import type { PriceProvider, PriceQuote, PriceSource } from '../pricing.types';
import { DexSwapModel } from '../../../ingestion/dex/models';
import { TokenFlowModel } from '../../flow/flow.model';

export class DexVwapSource implements PriceProvider {
  readonly name: PriceSource = 'DEX_VWAP';
  private limit = 200;
  
  async getUsdPrice(args: { chainId: number; token: string }): Promise<PriceQuote | null> {
    const token = args.token.toLowerCase();
    const chainId = args.chainId;
    
    try {
      // Get recent flows with USD volume for this token
      const flows = await TokenFlowModel.find({
        chainId,
        tokenAddress: token,
        usdVolume: { $gt: 0 },
      })
        .sort({ blockTime: -1 })
        .limit(this.limit)
        .lean();
      
      if (!flows || flows.length < 10) {
        // Not enough data for VWAP
        return null;
      }
      
      // Calculate volume-weighted average price
      // We need tokenVolume for this, but flows may not have it
      // Use usdVolume as proxy if tokenVolume not available
      
      let totalUsd = 0;
      let totalTokens = 0;
      let usableFlows = 0;
      
      for (const flow of flows) {
        if (flow.tokenVolume && flow.tokenVolume > 0) {
          totalUsd += flow.usdVolume;
          totalTokens += flow.tokenVolume;
          usableFlows++;
        }
      }
      
      if (totalTokens <= 0 || usableFlows < 5) {
        // Fallback: estimate from swap amounts
        const avgUsdPerFlow = flows.reduce((sum, f) => sum + f.usdVolume, 0) / flows.length;
        
        // Very rough estimate, low confidence
        return {
          chainId,
          token,
          priceUsd: avgUsdPerFlow / 1000, // Assuming ~1000 tokens per swap on average
          confidence: 0.15, // Very low confidence for this estimate
          source: 'DEX_VWAP',
          updatedAt: Date.now(),
          meta: { flowsUsed: flows.length, method: 'avgUsdEstimate' },
        };
      }
      
      const vwapPrice = totalUsd / totalTokens;
      
      if (!Number.isFinite(vwapPrice) || vwapPrice <= 0) {
        return null;
      }
      
      // Confidence based on sample size
      let confidence = 0.35;
      if (usableFlows >= 100) confidence = 0.45;
      if (usableFlows >= 50) confidence = 0.40;
      
      return {
        chainId,
        token,
        priceUsd: vwapPrice,
        confidence,
        source: 'DEX_VWAP',
        updatedAt: Date.now(),
        meta: { flowsUsed: usableFlows, totalUsd, totalTokens },
      };
    } catch (error) {
      console.error(`[DexVwapSource] Error fetching price for ${token}:`, error);
      return null;
    }
  }
}

export const dexVwapSource = new DexVwapSource();
console.log('[OnChain V2] DEX VWAP Price Source loaded');
