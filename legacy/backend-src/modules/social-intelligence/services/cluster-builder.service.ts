/**
 * Phase 0 — Cluster Builder
 *
 * Groups raw social events into semantic clusters.
 * 1 narrative = 1 cluster. Uses n-gram fingerprinting for dedup.
 * MUST run before echo/origin/propagation.
 */
import type { SocialEvent, SocialCluster } from '../types/social.types.js';

function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[@#]\w+/g, '')
    .replace(/[^\w\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function getNgrams(text: string, n: number): Set<string> {
  const words = text.split(' ').filter(w => w.length > 2);
  const grams = new Set<string>();
  for (let i = 0; i <= words.length - n; i++) {
    grams.add(words.slice(i, i + n).join(' '));
  }
  return grams;
}

function jaccardSimilarity(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0;
  let intersection = 0;
  for (const item of a) {
    if (b.has(item)) intersection++;
  }
  const union = a.size + b.size - intersection;
  return union > 0 ? intersection / union : 0;
}

function fingerprint(text: string): string {
  const norm = normalize(text);
  const words = norm.split(' ').filter(w => w.length > 3).sort();
  return words.slice(0, 8).join('_');
}

const SIMILARITY_THRESHOLD = 0.35;

export function buildClusters(events: SocialEvent[], asset: string): SocialCluster[] {
  if (!events.length) return [];

  const sorted = [...events].sort((a, b) => a.timestamp - b.timestamp);
  const clusters: SocialCluster[] = [];
  const assigned = new Set<string>();

  for (const event of sorted) {
    if (assigned.has(event.id)) continue;

    const normText = normalize(event.text);
    if (normText.length < 10) {
      assigned.add(event.id);
      continue;
    }

    const eventNgrams = getNgrams(normText, 3);

    // Try to merge into existing cluster
    let merged = false;
    for (const cluster of clusters) {
      const clusterNgrams = getNgrams(normalize(cluster.canonicalText), 3);
      const sim = jaccardSimilarity(eventNgrams, clusterNgrams);

      if (sim >= SIMILARITY_THRESHOLD) {
        cluster.events.push(event);
        assigned.add(event.id);
        merged = true;
        break;
      }
    }

    // New cluster
    if (!merged) {
      clusters.push({
        clusterId: `cl_${fingerprint(normText)}_${asset}`,
        canonicalText: event.text,
        events: [event],
        originEventId: null,
        asset,
      });
      assigned.add(event.id);
    }
  }

  return clusters;
}
