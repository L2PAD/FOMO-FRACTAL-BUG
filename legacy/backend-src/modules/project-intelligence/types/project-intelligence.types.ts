/**
 * Project Intelligence Types
 *
 * Core types for project-level reasoning:
 * tokenomics, unlock pressure, valuation, team/funds, launch structure, thesis.
 */

export type FdvLevel = 'LOW' | 'FAIR' | 'HIGH' | 'EXTREME';
export type FloatQuality = 'HEALTHY' | 'LOW' | 'DANGEROUS';
export type UnlockRisk = 'LOW' | 'MEDIUM' | 'HIGH';
export type ValuationLevel = 'CHEAP' | 'FAIR' | 'EXPENSIVE' | 'INSANE';
export type ProjectVerdict = 'STRONG' | 'MIXED' | 'WEAK';
export type QualityLevel = 'STRONG' | 'MID' | 'WEAK';

// ── Tokenomics ──
export interface TokenomicsAssessment {
  fdvLevel: FdvLevel;
  floatQuality: FloatQuality;
  unlockRisk: UnlockRisk;
  unlockInDays?: number;
  unlockPercent?: number;
  emissionRisk: number;        // 0–1
  utilityScore: number;        // 0–1
  verdict: QualityLevel;
  notes: string[];
}

// ── Unlock Pressure ──
export interface UnlockPressure {
  nextUnlockDays: number | null;
  unlockPercent: number;
  unlockImpactScore: number;   // 0–1
  insiderShare: number;        // 0–1 (% held by insiders/VCs)
  vestingMonthsLeft: number;
  riskLevel: UnlockRisk;
  notes: string[];
}

// ── Valuation ──
export interface ValuationAssessment {
  valuation: ValuationLevel;
  expectedRange: {
    low: number;
    base: number;
    high: number;
  };
  fdvToRevenue: number | null;
  fdvToTvl: number | null;
  narrativePremium: number;    // 0–1
  confidence: number;          // 0–1
  notes: string[];
}

// ── Team & Fund Quality ──
export interface TeamFundAssessment {
  teamScore: number;           // 0–1
  fundScore: number;           // 0–1
  insiderRisk: number;         // 0–1
  executionHistory: QualityLevel;
  verdict: QualityLevel;
  notes: string[];
}

// ── Launch Structure ──
export interface LaunchAssessment {
  launchQuality: number;       // 0–1
  distributionQuality: number; // 0–1
  mmRisk: number;              // 0–1 (market maker manipulation risk)
  dumpRisk: number;            // 0–1
  fairLaunch: boolean;
  verdict: QualityLevel;
  notes: string[];
}

// ── Project Thesis ──
export interface ProjectThesis {
  bullCase: string[];
  bearCase: string[];
  projectVerdict: ProjectVerdict;
  whatMarketMisses: string[];
  keyRisks: string[];
  overallScore: number;        // 0–1
}

// ── Full Project Intel ──
export interface ProjectIntel {
  asset: string;
  tokenomics: TokenomicsAssessment;
  unlockPressure: UnlockPressure;
  valuation: ValuationAssessment;
  teamFund: TeamFundAssessment;
  launch: LaunchAssessment;
  thesis: ProjectThesis;
  generatedAt: Date;
}

// ── Input: Project Profile (what we know about the project) ──
export interface ProjectProfile {
  asset: string;
  name: string;

  // Tokenomics
  totalSupply: number;
  circulatingSupply: number;
  maxSupply?: number;
  currentPrice: number;
  fdv: number;
  marketCap: number;

  // Unlock schedule
  nextUnlockDate?: string;     // ISO date
  nextUnlockPercent?: number;  // % of total supply
  vestingEndDate?: string;
  insiderAllocation?: number;  // 0–1 (% to team/VCs/insiders)

  // Traction
  dailyActiveUsers?: number;
  tvl?: number;
  dailyVolume?: number;
  revenue30d?: number;
  transactionCount30d?: number;

  // Team/Funds
  teamReputation?: QualityLevel;
  topFundsInvolved?: string[];
  totalFundingUsd?: number;
  previousProjects?: string[];

  // Launch
  launchType?: 'fair_launch' | 'ico' | 'ido' | 'vc_backed' | 'airdrop';
  initialFloat?: number;       // 0–1 (% circulating at launch)
  mmPresent?: boolean;

  // Context
  sector?: string;             // defi, l1, l2, gaming, meme, ai, rwa...
  launchDate?: string;
  narrative?: string;
}
