/**
 * EXCHANGE PUBLISHER JOB
 * ======================
 * 
 * Orchestrates Exchange prediction snapshot generation across all assets.
 */

import { publishExchangePredictionSnapshots } from '../modules/exchange/exchange-prediction.publisher.js';

// CRITICAL: Sync with WS-subscribed symbols (ALPHA_SYMBOLS + SECONDARY_SYMBOLS)
// BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, LINKUSDT
const ASSETS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'LINK'];

export async function runExchangePublisherJob(): Promise<void> {
  console.log('[ExchangePublisherJob] 🚀 Starting...');

  const results = { success: 0, failed: 0 };

  for (const asset of ASSETS) {
    try {
      const res = await publishExchangePredictionSnapshots(asset);
      if (res.ok) {
        results.success++;
      } else {
        results.failed++;
        console.log(`[ExchangePublisherJob] ⚠️  ${asset}: ${res.reason}`);
      }
    } catch (err: any) {
      results.failed++;
      console.error(`[ExchangePublisherJob] ❌ ${asset}:`, err.message);
    }
  }

  console.log(`[ExchangePublisherJob] ✅ Complete: ${results.success} success, ${results.failed} failed`);
}

export default runExchangePublisherJob;
