/**
 * Module Manifest Service
 * =========================
 * 
 * F1: Read manifest, check freeze status, gate mutations.
 */

import fs from 'fs';
import path from 'path';
import { getEvidenceWriterService } from './evidence-writer.service.js';

export interface ModuleManifest {
  moduleName: string;
  version: string;
  buildHash: string;
  frozen: boolean;
  decisionPolicyVersion: string;
  dataset: Record<string, any>;
  drift: Record<string, any>;
  risk: Record<string, any>;
  lifecycle: Record<string, any>;
  reliability: Record<string, any>;
  capitalGates: Record<string, any>;
  flags: Record<string, boolean>;
}

export interface FreezeCheckResult {
  frozen: boolean;
  envOverride: boolean;
  reason?: string;
}

export class ModuleManifestService {
  private manifestCache: ModuleManifest | null = null;
  private moduleName: 'sentiment-ml' | 'exchange-ml';
  private manifestPath: string;

  constructor(moduleName: 'sentiment-ml' | 'exchange-ml') {
    this.moduleName = moduleName;
    this.manifestPath = path.join(
      process.cwd(),
      'src/modules',
      moduleName,
      'module_manifest.json'
    );
  }

  /**
   * Load manifest from file
   */
  loadManifest(): ModuleManifest {
    if (this.manifestCache) return this.manifestCache;

    try {
      const content = fs.readFileSync(this.manifestPath, 'utf-8');
      const manifest = JSON.parse(content) as ModuleManifest;

      // Runtime overrides
      manifest.buildHash = process.env.GIT_SHA || process.env.BUILD_HASH || 'dev';

      this.manifestCache = manifest;
      return manifest;
    } catch (err) {
      console.error(`[Manifest] Failed to load ${this.manifestPath}:`, err);
      // Return minimal fallback
      return {
        moduleName: this.moduleName,
        version: '0.0.0',
        buildHash: 'unknown',
        frozen: false,
        decisionPolicyVersion: 'unknown',
        dataset: {},
        drift: {},
        risk: {},
        lifecycle: {},
        reliability: {},
        capitalGates: {},
        flags: {},
      };
    }
  }

  /**
   * Check if module is frozen (manifest + env override)
   */
  checkFreezeStatus(): FreezeCheckResult {
    const manifest = this.loadManifest();

    // ENV override: SENTIMENT_FROZEN=true or EXCHANGE_FROZEN=true
    const envKey = this.moduleName === 'sentiment-ml' ? 'SENTIMENT_FROZEN' : 'EXCHANGE_FROZEN';
    const envValue = process.env[envKey];

    if (envValue === 'true') {
      return { frozen: true, envOverride: true, reason: `${envKey}=true` };
    }

    if (manifest.frozen) {
      return { frozen: true, envOverride: false, reason: 'manifest.frozen=true' };
    }

    return { frozen: false, envOverride: false };
  }

  /**
   * Gate check for mutation operations
   * Returns error if frozen, null if allowed
   */
  async gateMutation(action: string): Promise<{ blocked: boolean; reason?: string }> {
    const freeze = this.checkFreezeStatus();

    if (freeze.frozen) {
      // Log evidence
      const evidence = getEvidenceWriterService();
      await evidence.append(
        this.moduleName === 'sentiment-ml' ? 'sentiment' : 'exchange',
        'freeze_blocked_action',
        'WARN',
        `Mutation blocked: ${action}`,
        { manifestVersion: this.loadManifest().version },
        { action, freezeReason: freeze.reason }
      );

      return {
        blocked: true,
        reason: `Module frozen (${freeze.reason}). Action '${action}' blocked.`,
      };
    }

    return { blocked: false };
  }

  /**
   * Get full manifest for API
   */
  getManifestForAPI(): ModuleManifest & { freezeStatus: FreezeCheckResult } {
    const manifest = this.loadManifest();
    const freezeStatus = this.checkFreezeStatus();

    return {
      ...manifest,
      freezeStatus,
    };
  }

  /**
   * Clear cache (for testing)
   */
  clearCache(): void {
    this.manifestCache = null;
  }
}

// Singletons
let sentimentManifestService: ModuleManifestService | null = null;
let exchangeManifestService: ModuleManifestService | null = null;

export function getSentimentManifestService(): ModuleManifestService {
  if (!sentimentManifestService) {
    sentimentManifestService = new ModuleManifestService('sentiment-ml');
  }
  return sentimentManifestService;
}

export function getExchangeManifestService(): ModuleManifestService {
  if (!exchangeManifestService) {
    exchangeManifestService = new ModuleManifestService('exchange-ml');
  }
  return exchangeManifestService;
}

console.log('[Shared] Module Manifest Service loaded (F1)');
