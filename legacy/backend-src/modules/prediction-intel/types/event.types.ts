/**
 * Event Types — raw events and interpreted events
 */

export type RawEvent = {
  id: string
  text: string
  sourceId: string
  sourceType: string
  asset: string | null
  timestamp: number
  entities: string[]
  tags: string[]
  severity: string
  payload: Record<string, any>
}

export type InterpretedEvent = {
  eventId: string
  relevance: number              // 0-1: how relevant to the target market
  direction: 'bullish' | 'bearish' | 'neutral'
  confidence: number             // 0-1: overall interpretation confidence

  impact: {
    probability: number          // delta to fair probability
    confidence: number           // delta to model confidence
    alignment: number            // delta to alignment score
  }

  meta: {
    novelty: number              // 0-1: how new is this info
    alreadyPriced: number        // 0-1: how much is already priced in
    timeHorizon: 'short' | 'mid' | 'long'
    resolutionRelevance: number  // 0-1: does it affect resolution
    narrativeRelevance: number   // 0-1: does it drive narrative/hype
  }

  signalConfidence: {
    sourceConfidence: number     // trust in source
    interpretationConfidence: number  // confidence in our interpretation
    marketRelevanceConfidence: number // confidence in market relevance
  }

  smartDriver: string            // human-readable explanation
}

export type EnrichedEvent = RawEvent & {
  extractedSource: string
  extractedSourceType: string
  extractedEntities: string[]
  extractedTags: string[]
}
