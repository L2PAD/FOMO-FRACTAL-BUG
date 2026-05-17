/**
 * runPerChain — Phase G0.4
 * =========================
 * 
 * Universal job wrapper that iterates over all enabled chains.
 * Every background job MUST use this to ensure chain-awareness.
 * 
 * Reads enabled chains from MongoDB chain registry (runtime state).
 * Falls back to static constants if DB unavailable.
 */

import { getActiveChainIds } from '../chains/chain.constants.js';

// Lazy import to avoid circular deps — reads enabled chains from DB
async function getEnabledChainIds(): Promise<number[]> {
  try {
    const mongoose = await import('mongoose');
    const db = mongoose.default.connection.db;
    if (!db) throw new Error('DB not connected');
    
    const chains = await db.collection('chains')
      .find({ enabled: true }, { projection: { chainId: 1, _id: 0 } })
      .toArray();
    
    if (chains.length > 0) {
      return chains.map(c => c.chainId as number);
    }
  } catch {
    // Fallback to static constants
  }
  return getActiveChainIds();
}

/**
 * Run a job function for each enabled chain sequentially.
 * Logs start/end per chain, catches per-chain errors without stopping the loop.
 */
export async function runPerChain(
  jobName: string,
  fn: (chainId: number) => Promise<void>
): Promise<{ chainId: number; ok: boolean; error?: string }[]> {
  const chainIds = await getEnabledChainIds();
  const results: { chainId: number; ok: boolean; error?: string }[] = [];

  for (const chainId of chainIds) {
    try {
      console.log(`[${jobName}] Running for chain=${chainId}`);
      await fn(chainId);
      results.push({ chainId, ok: true });
    } catch (err: any) {
      const msg = err?.message || String(err);
      console.error(`[${jobName}] Error on chain=${chainId}: ${msg}`);
      results.push({ chainId, ok: false, error: msg });
    }
  }

  return results;
}

console.log('[OnChain V2] runPerChain utility loaded');
