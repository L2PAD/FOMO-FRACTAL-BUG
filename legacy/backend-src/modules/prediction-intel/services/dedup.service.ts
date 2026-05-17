/**
 * Dedup Engine
 *
 * Deduplicates events by hash + similarity clustering.
 * If 20 identical tweets → 1 signal, not 20.
 */
import type { EnrichedEvent } from '../types/event.types.js';
import { dedupKey } from './novelty.service.js';

/**
 * Deduplicate a batch of events.
 * Keeps the first occurrence of each unique message.
 */
export function deduplicateEvents(events: EnrichedEvent[]): EnrichedEvent[] {
  const seen = new Map<string, EnrichedEvent>();

  for (const evt of events) {
    const key = dedupKey(evt.text);
    if (!seen.has(key)) {
      seen.set(key, evt);
    }
  }

  return Array.from(seen.values());
}

/**
 * Cluster similar events and return representative events.
 * Groups events with overlapping entities + similar text.
 */
export function clusterEvents(events: EnrichedEvent[]): EnrichedEvent[][] {
  const clusters: EnrichedEvent[][] = [];
  const assigned = new Set<string>();

  for (const evt of events) {
    if (assigned.has(evt.id)) continue;

    const cluster: EnrichedEvent[] = [evt];
    assigned.add(evt.id);

    for (const other of events) {
      if (assigned.has(other.id)) continue;
      if (isSameCluster(evt, other)) {
        cluster.push(other);
        assigned.add(other.id);
      }
    }

    clusters.push(cluster);
  }

  return clusters;
}

function isSameCluster(a: EnrichedEvent, b: EnrichedEvent): boolean {
  // Same entity overlap
  const entitiesA = new Set(a.entities);
  const entitiesB = new Set(b.entities);
  let overlap = 0;
  for (const e of entitiesA) {
    if (entitiesB.has(e)) overlap++;
  }
  if (overlap === 0) return false;

  // Similar tags
  const tagsA = new Set(a.tags);
  const tagsB = new Set(b.tags);
  let tagOverlap = 0;
  for (const t of tagsA) {
    if (tagsB.has(t)) tagOverlap++;
  }

  // Same cluster if entity + tag overlap
  return overlap > 0 && tagOverlap > 0;
}
