/**
 * META BRAIN V2 — PROVIDER REGISTRY
 * ==================================
 *
 * Single registry of all signal providers.
 * Adding a new module = 1 new provider + register here.
 * All consumers use getProviders() / getProviderCount() — never hardcoded numbers.
 *
 * Phase 7: Module Controller integration.
 * getActiveProviders() filters by feature flags from MongoDB.
 * getProviders() still returns ALL registered (for admin/status).
 */

import { MetaSignalProvider } from '../contracts/provider.contract.js';
import { FractalProvider } from '../providers/fractal.provider.js';
import { ExchangeProvider } from '../providers/exchange.provider.js';
import { OnChainProvider } from '../providers/onchain.provider.js';
import { SentimentProvider } from '../providers/sentiment.provider.js';

const META_PROVIDERS: MetaSignalProvider[] = [
  new FractalProvider(),
  new ExchangeProvider(),
  new OnChainProvider(),
  new SentimentProvider(),
];

/** Get all registered providers (including disabled — for admin/status) */
export function getProviders(): MetaSignalProvider[] {
  return META_PROVIDERS;
}

/** Total registered provider count (dynamic) */
export function getProviderCount(): number {
  return META_PROVIDERS.length;
}

/** Get provider by key */
export function getProvider(key: string): MetaSignalProvider | undefined {
  return META_PROVIDERS.find(p => p.key === key);
}

/** Get all provider keys */
export function getProviderKeys(): string[] {
  return META_PROVIDERS.map(p => p.key);
}

/**
 * Phase 7: Get only ACTIVE providers (filtered by Module Controller).
 * Returns providers whose module is enabled and mode !== 'off'.
 * Falls back to ALL providers if feature flags not yet initialized.
 */
export async function getActiveProviders(): Promise<MetaSignalProvider[]> {
  try {
    // Lazy import to avoid circular dependency at boot time
    const { getActiveModules } = await import('../services/module_controller.service.js');
    const activeModules = await getActiveModules();
    const activeKeys = new Set(activeModules.map(m => m.module));
    const filtered = META_PROVIDERS.filter(p => activeKeys.has(p.key));
    // Safety: if all modules got disabled somehow, return all
    return filtered.length > 0 ? filtered : META_PROVIDERS;
  } catch {
    // DB not ready or error — fall back to all providers
    return META_PROVIDERS;
  }
}

/**
 * Phase 7: Count of active providers (for coverage calculations).
 */
export async function getActiveProviderCount(): Promise<number> {
  const active = await getActiveProviders();
  return active.length;
}
