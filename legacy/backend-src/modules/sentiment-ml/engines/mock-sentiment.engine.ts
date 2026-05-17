/**
 * Mock Sentiment Engine
 * =====================
 * 
 * BLOCK 2A: Базовый sentiment engine (MOCK версия)
 * 
 * Будет заменён на:
 * - CNN model
 * - LLM-based analysis
 * - Ensemble
 * 
 * Сейчас: простой lexicon-based scorer
 */

export interface BaseSentimentResult {
  label: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  score: number;        // 0..1 (0 = bearish, 0.5 = neutral, 1 = bullish)
  confidence: 'LOW' | 'MEDIUM' | 'HIGH';
}

// Bullish keywords
const BULLISH_WORDS = new Set([
  'bullish', 'moon', 'pump', 'buy', 'long', 'breakout', 'ath', 'rally',
  'surge', 'soar', 'gain', 'profit', 'up', 'green', 'rocket', 'lambo',
  'accumulate', 'hodl', 'hold', 'strong', 'support', 'bounce', 'recovery',
  'undervalued', 'gem', 'alpha', 'wagmi', 'lfg', 'bullrun',
]);

// Bearish keywords
const BEARISH_WORDS = new Set([
  'bearish', 'dump', 'sell', 'short', 'crash', 'drop', 'fall', 'tank',
  'rekt', 'loss', 'down', 'red', 'scam', 'rug', 'ponzi', 'bubble',
  'overvalued', 'resistance', 'breakdown', 'ngmi', 'capitulation',
  'liquidation', 'fear', 'panic', 'dead', 'worthless',
]);

// Intensity modifiers
const INTENSIFIERS = new Set([
  'very', 'extremely', 'super', 'mega', 'ultra', 'insane', 'massive',
  'huge', 'crazy', 'absolutely', 'definitely', 'certainly',
]);

export class MockSentimentEngine {
  /**
   * Analyze text and return sentiment
   */
  analyze(text: string): BaseSentimentResult {
    const words = text.toLowerCase().split(/\W+/);
    
    let bullishScore = 0;
    let bearishScore = 0;
    let intensity = 1;
    
    for (let i = 0; i < words.length; i++) {
      const word = words[i];
      
      // Check intensifiers
      if (INTENSIFIERS.has(word)) {
        intensity = 1.5;
        continue;
      }
      
      // Check sentiment words
      if (BULLISH_WORDS.has(word)) {
        bullishScore += intensity;
        intensity = 1;
      } else if (BEARISH_WORDS.has(word)) {
        bearishScore += intensity;
        intensity = 1;
      }
    }
    
    // Calculate net sentiment
    const totalSignals = bullishScore + bearishScore;
    
    // No signals → neutral
    if (totalSignals === 0) {
      return {
        label: 'NEUTRAL',
        score: 0.5,
        confidence: 'LOW',
      };
    }
    
    // Calculate score (0 = bearish, 0.5 = neutral, 1 = bullish)
    const rawScore = bullishScore / totalSignals;
    const score = Math.max(0, Math.min(1, rawScore));
    
    // Determine label
    let label: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
    if (score > 0.6) {
      label = 'POSITIVE';
    } else if (score < 0.4) {
      label = 'NEGATIVE';
    } else {
      label = 'NEUTRAL';
    }
    
    // Determine confidence based on signal strength
    let confidence: 'LOW' | 'MEDIUM' | 'HIGH';
    if (totalSignals >= 4) {
      confidence = 'HIGH';
    } else if (totalSignals >= 2) {
      confidence = 'MEDIUM';
    } else {
      confidence = 'LOW';
    }
    
    return { label, score, confidence };
  }
}

// Singleton instance
export const mockSentimentEngine = new MockSentimentEngine();
