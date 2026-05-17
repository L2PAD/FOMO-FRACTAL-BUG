/**
 * Signal Normalizer
 *
 * Converts interpreted events into normalized signals
 * ready for injection into the prediction pipeline.
 */
import type { InterpretedEvent } from '../types/event.types.js';
import type { NormalizedSignal } from '../types/signal.types.js';

/**
 * Normalize an interpreted event into a pipeline-ready signal.
 */
export function normalizeSignal(event: InterpretedEvent): NormalizedSignal {
  return {
    eventId: event.eventId,
    bias: event.direction,
    strength: event.relevance * event.confidence,
    confidence: event.confidence,

    impact: {
      probability: event.impact.probability,
      confidence: event.impact.confidence,
      alignment: event.impact.alignment,
    },

    smartDriver: event.smartDriver,
    novelty: event.meta.novelty,
    alreadyPriced: event.meta.alreadyPriced,
  };
}

/**
 * Normalize a batch of interpreted events.
 */
export function normalizeSignals(events: InterpretedEvent[]): NormalizedSignal[] {
  return events
    .filter(e => e.relevance > 0.1)       // drop irrelevant
    .filter(e => e.meta.novelty > 0.05)    // drop pure repeats
    .map(normalizeSignal)
    .sort((a, b) => b.strength - a.strength);
}
