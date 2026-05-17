/**
 * META BRAIN V2 — REGIME POLICY PROFILES
 * ========================================
 *
 * Four profiles — one per market regime.
 * Each profile defines weights, thresholds, cooldown, gates, confidence penalties.
 *
 * TREND:      follow momentum, lower threshold, exchange/fractal dominate
 * RANGE:      avoid false breakouts, higher threshold, onchain/sentiment
 * RISK_OFF:   defensive, onchain/sentiment dominate, strict gates
 * TRANSITION: don't trust anyone, highest threshold, equal weights
 */

import { RegimePolicy } from './policy.contract.js';

export const META_BRAIN_POLICIES: Record<string, RegimePolicy> = {

  TREND: {
    regime: 'TREND',
    thresholds: { enter: 0.22, exit: 0.12 },
    cooldown: {
      '1':  20 * 60 * 1000,       // 20 min
      '7':  90 * 60 * 1000,       // 90 min
      '30': 4 * 60 * 60 * 1000,   // 4h
    },
    weights: {
      exchange:  0.45,  // ↑ increased from 0.38
      fractal:   0.35,  // ↑ increased from 0.30
      onchain:   0.10,  // ↓ decreased from 0.20 (LITE MODE)
      sentiment: 0.10,  // ↓ decreased from 0.12
    },
    gates: {
      minCoverage: 2,
      blockIfConflicted: false,
    },
    confidence: {
      entropyPenaltyK: 0.8,
      disagreementPenaltyK: 0.7,
      coveragePenaltyK: 0.6,
    },
  },

  RANGE: {
    regime: 'RANGE',
    thresholds: { enter: 0.35, exit: 0.18 },
    cooldown: {
      '1':  45 * 60 * 1000,       // 45 min
      '7':  3 * 60 * 60 * 1000,   // 3h
      '30': 8 * 60 * 60 * 1000,   // 8h
    },
    weights: {
      onchain:   0.15,  // ↓ decreased from 0.35 (LITE MODE)
      sentiment: 0.35,  // ↑ increased from 0.25
      exchange:  0.28,  // ↑ increased from 0.22
      fractal:   0.22,  // ↑ increased from 0.18
    },
    gates: {
      minCoverage: 3,
      blockIfConflicted: true,
    },
    confidence: {
      entropyPenaltyK: 1.2,
      disagreementPenaltyK: 1.0,
      coveragePenaltyK: 0.7,
    },
  },

  RISK_OFF: {
    regime: 'RISK_OFF',
    thresholds: { enter: 0.30, exit: 0.15 },
    cooldown: {
      '1':  30 * 60 * 1000,       // 30 min
      '7':  2 * 60 * 60 * 1000,   // 2h
      '30': 6 * 60 * 60 * 1000,   // 6h
    },
    weights: {
      onchain:   0.15,  // ↓ decreased from 0.42 (LITE MODE)
      sentiment: 0.38,  // ↑ increased from 0.28
      exchange:  0.27,  // ↑ increased from 0.18
      fractal:   0.20,  // ↑ increased from 0.12
    },
    gates: {
      minCoverage: 3,
      blockIfConflicted: false,
    },
    confidence: {
      entropyPenaltyK: 0.9,
      disagreementPenaltyK: 0.8,
      coveragePenaltyK: 0.8,
    },
  },

  TRANSITION: {
    regime: 'TRANSITION',
    thresholds: { enter: 0.40, exit: 0.22 },
    cooldown: {
      '1':  60 * 60 * 1000,       // 1h
      '7':  4 * 60 * 60 * 1000,   // 4h
      '30': 10 * 60 * 60 * 1000,  // 10h
    },
    weights: {
      exchange:  0.32,  // ↑ increased from 0.26
      fractal:   0.28,  // ↑ increased from 0.24
      onchain:   0.12,  // ↓ decreased from 0.26 (LITE MODE)
      sentiment: 0.28,  // ↑ increased from 0.24
    },
    gates: {
      minCoverage: 3,
      blockIfConflicted: true,
    },
    confidence: {
      entropyPenaltyK: 1.4,
      disagreementPenaltyK: 1.3,
      coveragePenaltyK: 1.0,
    },
  },
};
