/**
 * Sentiment SDK — Internal Module Interface
 * ==========================================
 * Direct import, no HTTP, no URLs, no ports.
 *
 * Usage:
 *   import { Sentiment } from '../core/sentiment/index.js'
 *
 *   const result = Sentiment.analyze("Bitcoin ETF approved", "twitter")
 *   const batch  = Sentiment.batch([{ id: "1", text: "Moon!" }], "news")
 *   const norm   = Sentiment.normalize("@user #BTC pumping https://t.co/x")
 *   const caps   = Sentiment.capabilities()
 */

import {
  analyze,
  analyzeBatch,
  normalize,
  getCapabilities,
  ENGINE_VERSION,
  RULESET_VERSION,
  type SentimentResult,
  type SentimentSource,
  type BatchResult,
  type NormalizeResult,
} from '../../modules/sentiment/sentiment.engine.js';

export class Sentiment {

  static readonly version = ENGINE_VERSION;
  static readonly ruleset = RULESET_VERSION;

  static analyze(text: string, source: SentimentSource = 'unknown'): SentimentResult {
    return analyze(text, source);
  }

  static batch(
    items: Array<{ id: string; text: string; source?: SentimentSource }>,
    defaultSource: SentimentSource = 'unknown',
  ): BatchResult {
    return analyzeBatch(items, defaultSource);
  }

  static normalize(text: string): NormalizeResult {
    return normalize(text);
  }

  static capabilities() {
    return getCapabilities();
  }
}

// Named re-exports for direct destructuring
export { analyze, analyzeBatch, normalize, getCapabilities, ENGINE_VERSION, RULESET_VERSION };
export type { SentimentResult, SentimentSource, BatchResult, NormalizeResult };
