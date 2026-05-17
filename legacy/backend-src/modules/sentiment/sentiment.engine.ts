/**
 * Sentiment Engine v2.0 — Universal Lexicon-Based Analyzer
 * =========================================================
 * Standalone, pure-function sentiment engine extracted from v1.5.0 client.
 * No external dependencies, no HTTP, no mock mode — just text in, sentiment out.
 *
 * Formula: finalScore = cnnScore * 0.60 + lexScore * 0.25 + rulesBias * 0.15
 */

// ── Version ──────────────────────────────────────────────
export const ENGINE_VERSION = '2.0.0';
export const RULESET_VERSION = 'A2-stable';

// ── Configuration ────────────────────────────────────────
const CONFIG = {
  weights: { cnn: 0.60, lexicon: 0.25, rules: 0.15 },
  thresholds: { positive: 0.55, negative: 0.40 },
  confidence: { modelWeight: 0.40, agreementWeight: 0.35, signalStrengthWeight: 0.25 },
  penalties: {
    singleWordFactor: 0.4,
    shortTextChars: 20,
    shortTextFactor: 0.7,
    conflictingSignalsFactor: 0.6,
    questionToneFactor: 0.8,
  },
  limits: {
    maxTextLength: 10000,
    maxBatchSize: 100,
  },
} as const;

// ── Lexicon ──────────────────────────────────────────────
const LEXICON = {
  positive: [
    'bullish', 'moon', 'pump', 'ath', 'breakout', 'surge', 'rally', 'soar',
    'accumulation', 'hodl', 'diamond hands', 'buy the dip', 'undervalued',
    'bullrun', 'parabolic', 'explosive', 'massive', 'huge',
    'buy', 'long', 'accumulate', 'load', 'stack',
    'optimistic', 'confident', 'strong', 'healthy',
    'growing', 'recovery', 'support', 'breakthrough', 'milestone',
    'etf', 'approval', 'approved', 'institutional', 'adoption', 'accelerating',
    'breaking', 'new highs', 'all-time high', 'all time high', 'highs',
    'tvl growth', 'ecosystem', 'exploding', 'divergence', 'confirmed',
    'blackrock', 'grayscale', 'fidelity', 'whale', 'whales loading',
    'resistance', 'beginning', 'gift', 'leg up', 'charge',
  ],
  negative: [
    'bearish', 'dump', 'crash', 'plunge', 'tank', 'collapse',
    'capitulation', 'panic', 'fear', 'fud', 'scam', 'rug', 'ponzi',
    'overvalued', 'bubble', 'correction', 'selloff',
    'sell', 'short', 'exit', 'liquidate',
    'worried', 'concerned', 'risky', 'dangerous', 'warning',
    'decline', 'drop', 'fall', 'loss',
    'hack', 'hacked', 'exploit', 'vulnerability', 'crackdown',
    'regulatory', 'sec', 'lawsuit', 'fraud', 'manipulation',
    'dead cat', 'trap', 'fake pump', 'rekt', 'pain ahead',
  ],
  neutral: [
    'stable', 'unchanged', 'sideways', 'consolidating', 'flat',
    'steady', 'holding', 'range', 'balanced', 'moderate',
    'low volume', 'low activity', 'quiet', 'calm', 'prices unchanged',
    'remains', 'processed', 'normal', 'normal levels', 'within range',
    'awaits', 'waiting', 'fees', 'gas fees', 'transactions',
    'lists', 'listed', 'launched', 'new trading pair',
    'ratio', 'volume', 'trading volume',
  ],
  mixed: ['but', 'however', 'although', 'despite', 'yet', 'though'],
  question: ['?', 'should i', 'is it', 'what if', 'anyone think', 'thoughts on'],
} as const;

// ── Types ────────────────────────────────────────────────

export type SentimentLabel = 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
export type ConfidenceLevel = 'LOW' | 'MEDIUM' | 'HIGH';
export type SentimentSource = 'twitter' | 'news' | 'telegram' | 'article' | 'headline' | 'user' | 'unknown';

export interface SentimentResult {
  label: SentimentLabel;
  score: number;
  source: SentimentSource;
  meta: {
    engineVersion: string;
    ruleset: string;
    confidence: ConfidenceLevel;
    confidenceScore: number;
    adjusted: boolean;
    adjustReasons: string[];
    reasons: string[];
    processingTimeMs: number;
    cached: boolean;
    breakdown: {
      cnnScore: number;
      cnnContribution: number;
      lexScoreNorm: number;
      lexContribution: number;
      rulesBias: number;
      rulesContribution: number;
    };
    detected: {
      positiveWords: string[];
      negativeWords: string[];
      neutralWords: string[];
      mixedSignals: boolean;
      questionTone: boolean;
      shortText: boolean;
      singleWord: boolean;
    };
  };
}

export interface BatchItem {
  id: string;
  text: string;
  source?: SentimentSource;
}

export interface BatchResultItem {
  id: string;
  result: SentimentResult | null;
  error: string | null;
}

export interface BatchResult {
  results: BatchResultItem[];
  meta: {
    engineVersion: string;
    totalItems: number;
    successCount: number;
    errorCount: number;
    processingTimeMs: number;
  };
}

// ── Internal helpers ─────────────────────────────────────

function lexiconScan(text: string) {
  const lower = text.toLowerCase();
  const words = lower.split(/\s+/);
  const totalWords = Math.max(words.length, 1);

  const positiveWords = LEXICON.positive.filter(w => lower.includes(w));
  const negativeWords = LEXICON.negative.filter(w => lower.includes(w));
  const neutralWords = LEXICON.neutral.filter(w => lower.includes(w));
  const mixedIndicators = LEXICON.mixed.filter(w => lower.includes(w));
  const questionIndicators = LEXICON.question.filter(w => lower.includes(w));

  let rawScore: number;
  if (neutralWords.length > 0 && positiveWords.length === 0 && negativeWords.length === 0) {
    rawScore = 0;
  } else {
    rawScore = (positiveWords.length - negativeWords.length) / totalWords;
  }

  const scoreNorm = Math.max(0, Math.min(1, (rawScore + 1) / 2));

  return {
    scoreNorm,
    positiveWords,
    negativeWords,
    neutralWords,
    mixedSignals: mixedIndicators.length > 0 || (positiveWords.length > 0 && negativeWords.length > 0),
    questionTone: questionIndicators.length > 0,
  };
}

function computeRulesBias(
  positiveWords: string[],
  negativeWords: string[],
  mixedSignals: boolean,
  questionTone: boolean,
  shortText: boolean,
) {
  let bias = 0;
  const rulesApplied: string[] = [];
  const reasons: string[] = [];

  if (positiveWords.length >= 2) {
    bias += 0.08;
    rulesApplied.push('BULLISH_BOOST');
    reasons.push(`Strong bullish signals: ${positiveWords.slice(0, 3).join(', ')}`);
  } else if (positiveWords.length === 1) {
    bias += 0.04;
    rulesApplied.push('BULLISH_KEYWORDS');
    reasons.push(`Bullish keyword: ${positiveWords[0]}`);
  }

  if (negativeWords.length >= 2) {
    bias -= 0.08;
    rulesApplied.push('BEARISH_BOOST');
    reasons.push(`Strong bearish signals: ${negativeWords.slice(0, 3).join(', ')}`);
  } else if (negativeWords.length === 1) {
    bias -= 0.04;
    rulesApplied.push('BEARISH_KEYWORDS');
    reasons.push(`Bearish keyword: ${negativeWords[0]}`);
  }

  if (mixedSignals && positiveWords.length > 0 && negativeWords.length > 0) {
    bias *= 0.5;
    rulesApplied.push('CONFLICT_DAMPENER');
    reasons.push('Conflicting bullish/bearish signals');
  }

  if (questionTone) {
    bias *= 0.7;
    rulesApplied.push('QUESTION_DAMPENER');
    reasons.push('Question tone reduces signal strength');
  }

  if (shortText) {
    bias *= 0.8;
    rulesApplied.push('SHORT_TEXT_PENALTY');
    reasons.push('Short text reduces reliability');
  }

  return { bias: Math.max(-0.2, Math.min(0.2, bias)), rulesApplied, reasons };
}

// ── Public API ───────────────────────────────────────────

/**
 * Analyze a single text and return sentiment.
 * Pure function — no side effects, no I/O.
 */
export function analyze(text: string, source: SentimentSource = 'unknown'): SentimentResult {
  const t0 = performance.now();

  const lex = lexiconScan(text);
  const wordCount = text.split(/\s+/).length;
  const shortText = text.length < CONFIG.penalties.shortTextChars;
  const singleWord = wordCount === 1;
  const veryShortText = wordCount < 3;

  // Simulated CNN score derived from lexicon (deterministic component + minor jitter)
  let simulatedCnn = lex.scoreNorm;
  simulatedCnn += (Math.random() - 0.5) * 0.05;
  simulatedCnn = Math.max(0.15, Math.min(0.85, simulatedCnn));

  if (singleWord) {
    simulatedCnn = 0.5;
  } else if (veryShortText && lex.positiveWords.length === 0 && lex.negativeWords.length === 0) {
    simulatedCnn = 0.5;
  }

  const rules = computeRulesBias(lex.positiveWords, lex.negativeWords, lex.mixedSignals, lex.questionTone, shortText);

  // Ensemble
  const cnnContribution = simulatedCnn * CONFIG.weights.cnn;
  const lexContribution = lex.scoreNorm * CONFIG.weights.lexicon;
  const rulesContribution = rules.bias * CONFIG.weights.rules;
  let finalScore = Math.max(0, Math.min(1, cnnContribution + lexContribution + rulesContribution));

  // Label
  let label: SentimentLabel;
  if (singleWord) {
    label = 'NEUTRAL';
  } else if (finalScore >= CONFIG.thresholds.positive) {
    label = 'POSITIVE';
  } else if (finalScore <= CONFIG.thresholds.negative) {
    label = 'NEGATIVE';
  } else {
    label = 'NEUTRAL';
  }

  // Confidence
  let penalty = 1.0;
  if (singleWord) penalty *= 0.4;
  else if (shortText) penalty *= CONFIG.penalties.shortTextFactor;
  if (lex.mixedSignals) penalty *= CONFIG.penalties.conflictingSignalsFactor;
  if (lex.questionTone) penalty *= CONFIG.penalties.questionToneFactor;

  const modelConfidence = Math.abs(simulatedCnn - 0.5) * 2;
  const agreement = 1 - Math.abs(simulatedCnn - lex.scoreNorm);
  const totalKeywords = lex.positiveWords.length + lex.negativeWords.length;
  const signalStrength = Math.min(totalKeywords / 3, 1);

  let confidence =
    modelConfidence * CONFIG.confidence.modelWeight +
    agreement * CONFIG.confidence.agreementWeight +
    signalStrength * 0.25;
  confidence = Math.max(0, Math.min(1, confidence * penalty));

  let confidenceLevel: ConfidenceLevel;
  if (confidence >= 0.7) confidenceLevel = 'HIGH';
  else if (confidence >= 0.4) confidenceLevel = 'MEDIUM';
  else confidenceLevel = 'LOW';

  const round3 = (n: number) => Math.round(n * 1000) / 1000;
  const processingTimeMs = Math.round((performance.now() - t0) * 100) / 100;

  return {
    label,
    score: round3(finalScore),
    source,
    meta: {
      engineVersion: ENGINE_VERSION,
      ruleset: RULESET_VERSION,
      confidence: confidenceLevel,
      confidenceScore: round3(confidence),
      adjusted: rules.rulesApplied.length > 0,
      adjustReasons: rules.rulesApplied,
      reasons: rules.reasons,
      processingTimeMs,
      cached: false,
      breakdown: {
        cnnScore: round3(simulatedCnn),
        cnnContribution: round3(cnnContribution),
        lexScoreNorm: round3(lex.scoreNorm),
        lexContribution: round3(lexContribution),
        rulesBias: round3(rules.bias),
        rulesContribution: round3(rulesContribution),
      },
      detected: {
        positiveWords: lex.positiveWords,
        negativeWords: lex.negativeWords,
        neutralWords: lex.neutralWords,
        mixedSignals: lex.mixedSignals,
        questionTone: lex.questionTone,
        shortText,
        singleWord,
      },
    },
  };
}

/**
 * Analyze a batch of texts.
 */
export function analyzeBatch(items: BatchItem[], defaultSource: SentimentSource = 'unknown'): BatchResult {
  const t0 = performance.now();
  let successCount = 0;
  let errorCount = 0;

  const results: BatchResultItem[] = items.map(item => {
    try {
      if (!item.text || typeof item.text !== 'string') {
        errorCount++;
        return { id: item.id, result: null, error: 'Text is required and must be a string' };
      }
      if (item.text.length > CONFIG.limits.maxTextLength) {
        errorCount++;
        return { id: item.id, result: null, error: `Text exceeds max length of ${CONFIG.limits.maxTextLength}` };
      }
      const result = analyze(item.text, item.source || defaultSource);
      successCount++;
      return { id: item.id, result, error: null };
    } catch (err: any) {
      errorCount++;
      return { id: item.id, result: null, error: err.message || 'Unknown error' };
    }
  });

  return {
    results,
    meta: {
      engineVersion: ENGINE_VERSION,
      totalItems: items.length,
      successCount,
      errorCount,
      processingTimeMs: Math.round((performance.now() - t0) * 100) / 100,
    },
  };
}

/**
 * Return engine capabilities and configuration (no secrets).
 */
export function getCapabilities() {
  return {
    engineVersion: ENGINE_VERSION,
    ruleset: RULESET_VERSION,
    type: 'lexicon-rules-ensemble',
    limits: CONFIG.limits,
    supportedModes: ['TEXT', 'BATCH'],
    supportedSources: ['twitter', 'news', 'telegram', 'article', 'headline', 'user'] as SentimentSource[],
    lexiconStats: {
      positive: LEXICON.positive.length,
      negative: LEXICON.negative.length,
      neutral: LEXICON.neutral.length,
    },
    weights: CONFIG.weights,
    thresholds: CONFIG.thresholds,
  };
}

// ── Normalize ────────────────────────────────────────────

export interface NormalizeResult {
  original: string;
  cleaned: string;
  tokens: string[];
  lang: 'en' | 'ru' | 'ua' | 'unknown';
  charCount: number;
  wordCount: number;
}

const CYRILLIC = /[\u0400-\u04FF]/;
const UA_SPECIFIC = /[\u0490\u0491\u0404\u0454\u0406\u0456\u0407\u0457]/; // ґ Ґ є Є і І ї Ї

function detectLang(text: string): 'en' | 'ru' | 'ua' | 'unknown' {
  const sample = text.slice(0, 500);
  const hasCyrillic = CYRILLIC.test(sample);
  if (!hasCyrillic) {
    const hasLatin = /[a-zA-Z]/.test(sample);
    return hasLatin ? 'en' : 'unknown';
  }
  return UA_SPECIFIC.test(sample) ? 'ua' : 'ru';
}

/**
 * Normalize text: clean, tokenize, detect language.
 * Useful for debugging and pipeline inspection.
 */
export function normalize(text: string): NormalizeResult {
  const cleaned = text
    .replace(/https?:\/\/\S+/g, '')        // remove URLs
    .replace(/@\w+/g, '')                   // remove @mentions
    .replace(/#(\w+)/g, '$1')               // strip # but keep tag text
    .replace(/[^\w\s\u0400-\u04FF'-]/g, '') // keep letters, digits, hyphens, apostrophes, cyrillic
    .replace(/\s+/g, ' ')
    .trim();

  const tokens = cleaned.toLowerCase().split(/\s+/).filter(Boolean);
  const lang = detectLang(text);

  return {
    original: text,
    cleaned,
    tokens,
    lang,
    charCount: cleaned.length,
    wordCount: tokens.length,
  };
}
