/**
 * Sentiment Weighting Service
 * ===========================
 * 
 * BLOCK 3: Deterministic Weighting v1
 * 
 * Превращает baseScore (0-1) в market-relevant сигнал с учётом:
 * - Author weight (авторитет)
 * - Influence weight (влияние)
 * - Bot penalty (антибот защита)
 * - Time decay (временное затухание)
 * 
 * Формула устойчива к манипуляциям и детерминистична.
 */

export type BaseConfidence = 'LOW' | 'MEDIUM' | 'HIGH';

export interface WeightingResult {
  weightedScore: number;        // 0..1
  weightedConfidence: number;   // 0..1
  meta: {
    authorWeight: number;       // 0.5..1
    influenceWeight: number;    // 0.5..1
    botPenalty: number;         // 0.3..1
    timeDecay: number;          // 0..1
    finalWeight: number;        // combined weight
  };
}

export interface WeightingInput {
  baseScore: number;            // 0..1
  baseConfidence: BaseConfidence;
  tweetCreatedAt: string | Date;
  
  // Enrichment (optional)
  authorScore?: number;         // 0..1
  influence?: number;           // 0..1
  botProb?: number;             // 0..1
  
  // Override timestamp for testing
  nowTs?: number;
}

/**
 * Clamp value to 0..1 range
 */
function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

export class SentimentWeightingService {
  /**
   * Compute weighted score and confidence for a sentiment event
   */
  compute(args: WeightingInput): WeightingResult {
    const nowTs = args.nowTs ?? Date.now();
    const t0 = new Date(args.tweetCreatedAt).getTime();

    // 1) Center base score: 0..1 → -1..+1
    const base = clamp01(args.baseScore);
    const baseCentered = (base - 0.5) * 2; // [-1..+1]

    // 2) Author weight: higher author score → higher weight
    // authorScore 0 → weight 0.5
    // authorScore 1 → weight 1.0
    const authorScore = clamp01(args.authorScore ?? 0.5);
    const authorWeight = 0.5 + authorScore * 0.5; // [0.5..1]

    // 3) Influence weight: same logic
    const influence = clamp01(args.influence ?? 0.5);
    const influenceWeight = 0.5 + influence * 0.5; // [0.5..1]

    // 4) Bot penalty: high bot probability → low weight
    // botProb 0 → penalty 1.0 (no penalty)
    // botProb 1 → penalty 0.3 (70% penalty)
    const botProb = clamp01(args.botProb ?? 0);
    const botPenalty = 1 - botProb * 0.7; // [0.3..1]

    // 5) Time decay: exponential decay with ~48h half-life
    // Fresh tweet → decay ~1
    // 48h old → decay ~0.5
    // 96h old → decay ~0.25
    const ageHours = Math.max(0, (nowTs - t0) / 3600000);
    const timeDecay = Math.exp(-ageHours / 48); // (0..1]

    // 6) Final weight: multiply all factors
    const finalWeight = authorWeight * influenceWeight * botPenalty * timeDecay;

    // 7) Apply weight to centered score, then convert back to 0..1
    const weightedCentered = baseCentered * finalWeight;
    const weightedScore = clamp01(weightedCentered / 2 + 0.5);

    // 8) Weighted confidence
    const confMap: Record<BaseConfidence, number> = {
      HIGH: 1.0,
      MEDIUM: 0.7,
      LOW: 0.4,
    };
    const baseConf = confMap[args.baseConfidence] ?? 0.5;
    const weightedConfidence = clamp01(finalWeight * baseConf);

    return {
      weightedScore,
      weightedConfidence,
      meta: {
        authorWeight,
        influenceWeight,
        botPenalty,
        timeDecay,
        finalWeight,
      },
    };
  }
}

// Singleton instance
export const sentimentWeightingService = new SentimentWeightingService();
