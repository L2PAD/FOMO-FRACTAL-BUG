/**
 * Dedupe Service
 * ==============
 * Two-level deduplication:
 * Level 1: sourceType + externalId (hard unique key)
 * Level 2: SHA-1 hash of normalized text + author + time bucket (soft fallback)
 */

import { createHash } from 'crypto';
import type { UnifiedTextEvent } from '../ingestion.types.js';

class DedupeService {
  /**
   * Build a dedupe key for an event.
   * If externalId exists, uses hard key. Otherwise falls back to content hash.
   */
  buildDedupeKey(event: UnifiedTextEvent): string {
    if (event.externalId) {
      return `${event.sourceType}:${event.externalId}`;
    }

    const normalizedText = (event.text || '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim();

    // 15-minute time bucket
    const bucketTs = new Date(
      Math.floor(event.publishedAt.getTime() / (15 * 60 * 1000)) * (15 * 60 * 1000)
    ).toISOString();

    const raw = `${event.sourceType}|${normalizedText}|${event.author?.handle ?? ''}|${bucketTs}`;

    return createHash('sha1').update(raw).digest('hex');
  }
}

export const dedupeService = new DedupeService();
