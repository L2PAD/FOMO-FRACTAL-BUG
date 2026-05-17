/**
 * Novelty Engine
 *
 * Scores how novel an event is relative to recent events.
 * Repeated info = low novelty = low signal weight.
 */

const SIMILARITY_THRESHOLD = 0.6;

/**
 * Compute novelty of an event against recent event texts.
 * @returns 0-1 (1 = completely novel, 0 = pure repeat)
 */
export function computeNovelty(eventText: string, recentTexts: string[]): number {
  if (!recentTexts.length) return 1.0;

  let highSimilarityHits = 0;
  const normalized = normalize(eventText);

  for (const recent of recentTexts) {
    const sim = similarity(normalized, normalize(recent));
    if (sim > SIMILARITY_THRESHOLD) {
      highSimilarityHits++;
    }
  }

  if (highSimilarityHits === 0) return 1.0;
  if (highSimilarityHits === 1) return 0.7;
  if (highSimilarityHits <= 3) return 0.4;
  if (highSimilarityHits <= 6) return 0.2;
  return 0.05;  // echo chamber
}

/**
 * Hash-based dedup key for exact/near-exact matches.
 */
export function dedupKey(text: string): string {
  return normalize(text).slice(0, 120);
}

function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Token overlap similarity (Jaccard).
 */
function similarity(a: string, b: string): number {
  const tokensA = new Set(a.split(' '));
  const tokensB = new Set(b.split(' '));

  if (tokensA.size === 0 || tokensB.size === 0) return 0;

  let intersection = 0;
  for (const t of tokensA) {
    if (tokensB.has(t)) intersection++;
  }

  const union = tokensA.size + tokensB.size - intersection;
  return union > 0 ? intersection / union : 0;
}
