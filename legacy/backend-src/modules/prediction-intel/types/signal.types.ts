/**
 * Signal Types — normalized signals ready for pipeline injection
 */

export type NormalizedSignal = {
  eventId: string
  bias: 'bullish' | 'bearish' | 'neutral'
  strength: number               // 0-1
  confidence: number             // 0-1

  impact: {
    probability: number          // delta
    confidence: number           // delta
    alignment: number            // delta
  }

  smartDriver: string            // human explanation
  novelty: number
  alreadyPriced: number
}

export type SignalBatch = {
  marketId: string
  asset: string
  signals: NormalizedSignal[]
  aggregated: {
    netProbabilityImpact: number
    netConfidenceImpact: number
    netAlignmentImpact: number
    dominantBias: 'bullish' | 'bearish' | 'neutral'
    signalCount: number
    avgNovelty: number
    avgAlreadyPriced: number
    topDriver: string
  }
}
