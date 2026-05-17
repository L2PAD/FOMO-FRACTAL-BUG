/**
 * FRACTAL PUBLISHER JOB
 * =====================
 * 
 * Orchestrates Fractal forecast snapshot generation across all assets.
 */

import { publishFractalForecastSnapshot } from '../modules/fractal/fractal-forecast.publisher.js';

const ASSETS = ['BTC', 'ETH', 'SOL', 'ARB', 'OP', 'AVAX', 'MATIC'];

export async function runFractalPublisherJob(): Promise<void> {
  console.log('[FractalPublisherJob] 🚀 Starting...');

  const results = { success: 0, failed: 0, skipped: 0 };

  for (const asset of ASSETS) {
    try {
      const res = await publishFractalForecastSnapshot(asset);
      if (res.ok) {
        results.success++;
      } else {
        if (res.reason === 'bootstrap_only' || res.reason === 'no_state') {
          results.skipped++;
        } else {
          results.failed++;
        }
        console.log(`[FractalPublisherJob] ⚠️  ${asset}: ${res.reason}`);
      }
    } catch (err: any) {
      results.failed++;
      console.error(`[FractalPublisherJob] ❌ ${asset}:`, err.message);
    }
  }

  console.log(`[FractalPublisherJob] ✅ Complete: ${results.success} success, ${results.skipped} skipped, ${results.failed} failed`);
}

export default runFractalPublisherJob;
