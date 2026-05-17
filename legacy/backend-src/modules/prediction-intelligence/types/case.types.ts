/**
 * Case Intelligence Types — Case Input, Evidence, and Decision Memo
 */

export type CaseInput = {
  marketId: string;
  question: string;

  decoded: {
    eventType: string;
    entities: string[];
    deadline?: string;
    asset: string;
    comparator?: string;
    threshold?: number;
  };

  marketState: {
    impliedProb: number;
    liquidity: number;
    volume24h: number;
    spread: number;
    move1h?: number;
    move6h?: number;
  };

  signals: {
    sentiment: any[];
    onchain: any[];
    news: any[];
    twitter: any[];
  };

  context: {
    exchange?: any;
    fractal?: any;
  };
};

export type EventUnderstanding = {
  eventClass: 'catalyst' | 'threshold' | 'launch' | 'listing';
  actors: string[];
  objects: string[];
  action: string;
  resolution: {
    sourceOfTruth: string;
    requiredProofs: string[];
    invalidProofs: string[];
  };
  dependencies: string[];
  timeSensitivity: 'low' | 'medium' | 'high';
};

export type EvidenceItem = {
  id: string;
  text: string;
  source: string;
  sourceType: 'official' | 'media' | 'social' | 'onchain' | 'exchange' | 'unknown';
  sourceTier: 'tier1' | 'tier2' | 'tier3';
  timestamp: number;
  entities: string[];
  eventTags: string[];
};

export type EvidencePack = {
  primary: EvidenceItem[];
  secondary: EvidenceItem[];
  narrative: EvidenceItem[];
  echo: EvidenceItem[];
  contradictory: EvidenceItem[];
  onchain: EvidenceItem[];
};

export type ClassifiedEvidence = {
  highSignal: EvidenceItem[];
  mediumSignal: EvidenceItem[];
  lowSignal: EvidenceItem[];
  noise: EvidenceItem[];
};

export type WeightedEvidence = EvidenceItem & {
  weight: number;
  role: 'driver' | 'confirmation' | 'noise' | 'contradiction';
  dimensions: {
    trust: number;
    novelty: number;
    relevance: number;
    resolutionImpact: number;
    narrativeImpact: number;
    pricedIn: number;
  };
};

export type ThesisResult = {
  bullCase: {
    arguments: string[];
    strength: number;
  };
  bearCase: {
    arguments: string[];
    strength: number;
  };
  neutralCase: {
    arguments: string[];
  };
};

export type MarketGap = {
  pricedInLevel: number;
  marketKnows: string[];
  marketMisses: string[];
  mispricingType: 'underreaction' | 'overreaction' | 'correct';
};

export type RiskItem = {
  type: 'resolution' | 'timing' | 'false_signal' | 'liquidity' | 'wording';
  severity: number;
  description: string;
};

export type RiskMap = {
  risks: RiskItem[];
  invalidators: string[];
};

export type DecisionMemo = {
  summary: string;
  thesis: string;
  counterThesis: string;
  keyDrivers: string[];
  keyRisks: string[];
  whatMarketPricesIn: string[];
  whatMarketMisses: string[];
  action: 'YES_NOW' | 'NO_NOW' | 'WAIT' | 'AVOID';
  conviction: 'HIGH' | 'MEDIUM' | 'LOW';
  whyNow: string[];
  whyNot: string[];
};
