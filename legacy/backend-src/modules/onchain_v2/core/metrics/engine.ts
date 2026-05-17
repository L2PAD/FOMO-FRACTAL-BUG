/**
 * OnChain V2 — Metrics Engine
 * ============================
 * 
 * Transform raw snapshots into normalized measurements.
 * 
 * FORMULAS (LOCKED v2):
 * - flowScore: net capital flow direction
 * - exchangePressure: sell vs withdraw pressure on exchanges
 * - whaleActivity: large holder participation
 * - networkHeat: network congestion/activity level
 * - velocity: capital movement speed
 * - distributionSkew: activity concentration
 * 
 * INVARIANTS:
 * - NO verdict, NO signals, NO predictions
 * - NO knowledge of Exchange or Sentiment or MetaBrain
 * - Pure measurement layer
 */

import {
  OnchainSnapshot,
  OnchainMetrics,
  OnchainWindow,
  ONCHAIN_THRESHOLDS,
} from '../contracts.js';

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const EPS = 1e-10;

const EXPECTED_FIELDS = [
  'exchangeInflowUsd', 'exchangeOutflowUsd',
  'netInflowUsd', 'netOutflowUsd',
  'activeAddresses', 'txCount', 'feesUsd',
  'largeTransfersCount', 'largeTransfersVolumeUsd',
];

const DRIVER_THRESHOLDS = {
  highFlow: 0.5,
  highPressure: 0.4,
  highWhale: 0.6,
  highHeat: 0.7,
  highVelocity: 0.6,
  highSkew: 0.7,
};

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════════

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function normalizeRatio(a: number, b: number): number {
  const sum = Math.abs(a) + Math.abs(b) + EPS;
  return clamp((a - b) / sum, -1, 1);
}

function normalizeLog(value: number, maxValue: number): number {
  if (value <= 0) return 0;
  return clamp(Math.log(value + 1) / Math.log(maxValue + 1), 0, 1);
}

// ═══════════════════════════════════════════════════════════════
// METRIC CALCULATIONS (LOCKED v2)
// ═══════════════════════════════════════════════════════════════

function calcFlowScore(snapshot: OnchainSnapshot): number {
  const inflow = snapshot.netInflowUsd || 0;
  const outflow = snapshot.netOutflowUsd || 0;
  return normalizeRatio(outflow, inflow);
}

function calcExchangePressure(snapshot: OnchainSnapshot): number {
  const deposits = snapshot.exchangeInflowUsd || 0;
  const withdrawals = snapshot.exchangeOutflowUsd || 0;
  return normalizeRatio(deposits, withdrawals);
}

function calcWhaleActivity(snapshot: OnchainSnapshot): number {
  const volume = snapshot.largeTransfersVolumeUsd || 0;
  const count = snapshot.largeTransfersCount || 0;
  
  const maxVolume = 1_000_000_000;
  
  const volumeScore = normalizeLog(volume, maxVolume);
  const countScore = normalizeLog(count * ONCHAIN_THRESHOLDS.LARGE_TRANSFER_USD, maxVolume);
  
  return clamp((volumeScore * 0.7 + countScore * 0.3), 0, 1);
}

function calcNetworkHeat(snapshot: OnchainSnapshot): number {
  const maxAddresses = 100_000;
  const maxTxCount = 100_000;
  const maxFees = 500_000;
  
  const addressScore = normalizeLog(snapshot.activeAddresses || 0, maxAddresses);
  const txScore = normalizeLog(snapshot.txCount || 0, maxTxCount);
  const feeScore = normalizeLog(snapshot.feesUsd || 0, maxFees);
  
  return clamp(addressScore * 0.3 + txScore * 0.4 + feeScore * 0.3, 0, 1);
}

function calcVelocity(snapshot: OnchainSnapshot): number {
  const totalVolume = Math.abs(snapshot.netInflowUsd || 0) + 
                      Math.abs(snapshot.netOutflowUsd || 0) +
                      (snapshot.largeTransfersVolumeUsd || 0);
  
  const maxVelocity = 10_000_000_000;
  return normalizeLog(totalVolume, maxVelocity);
}

function calcDistributionSkew(snapshot: OnchainSnapshot): number {
  const largeVolume = snapshot.largeTransfersVolumeUsd || 0;
  const totalVolume = Math.abs(snapshot.netInflowUsd || 0) + 
                      Math.abs(snapshot.netOutflowUsd || 0) + EPS;
  
  const skew = largeVolume / (largeVolume + totalVolume);
  return clamp(skew, 0, 1);
}

function calcDataCompleteness(snapshot: OnchainSnapshot): number {
  let available = 0;
  
  for (const field of EXPECTED_FIELDS) {
    const value = (snapshot as any)[field];
    if (value !== undefined && value !== null && value !== 0) {
      available++;
    }
  }
  
  return available / EXPECTED_FIELDS.length;
}

function calcConfidence(snapshot: OnchainSnapshot, completeness: number): number {
  const sourceQuality = snapshot.sourceQuality || 0.3;
  
  const ageMs = Date.now() - snapshot.snapshotTimestamp;
  const freshness = ageMs < 300_000 ? 1.0 : 
                    ageMs < 600_000 ? 0.8 : 
                    ageMs < 3600_000 ? 0.5 : 0.3;
  
  return clamp(completeness * sourceQuality * freshness, 0, 1);
}

function generateDrivers(
  flowScore: number,
  exchangePressure: number,
  whaleActivity: number,
  networkHeat: number,
  velocity: number,
  distributionSkew: number
): string[] {
  const drivers: string[] = [];
  
  if (flowScore > DRIVER_THRESHOLDS.highFlow) {
    drivers.push('net_outflows_detected');
  } else if (flowScore < -DRIVER_THRESHOLDS.highFlow) {
    drivers.push('net_inflows_detected');
  }
  
  if (exchangePressure > DRIVER_THRESHOLDS.highPressure) {
    drivers.push('exchange_deposits_elevated');
  } else if (exchangePressure < -DRIVER_THRESHOLDS.highPressure) {
    drivers.push('exchange_withdrawals_elevated');
  }
  
  if (whaleActivity > DRIVER_THRESHOLDS.highWhale) {
    drivers.push('large_holder_activity_spike');
  }
  
  if (networkHeat > DRIVER_THRESHOLDS.highHeat) {
    drivers.push('network_congestion_high');
  }
  
  if (velocity > DRIVER_THRESHOLDS.highVelocity) {
    drivers.push('capital_velocity_elevated');
  }
  
  if (distributionSkew > DRIVER_THRESHOLDS.highSkew) {
    drivers.push('activity_concentrated');
  }
  
  return drivers.slice(0, 3);
}

// ═══════════════════════════════════════════════════════════════
// METRICS ENGINE
// ═══════════════════════════════════════════════════════════════

export class OnchainMetricsEngine {
  /**
   * Calculate all metrics from a snapshot
   */
  calculate(snapshot: OnchainSnapshot): OnchainMetrics {
    const flowScore = calcFlowScore(snapshot);
    const exchangePressure = calcExchangePressure(snapshot);
    const whaleActivity = calcWhaleActivity(snapshot);
    const networkHeat = calcNetworkHeat(snapshot);
    const velocity = calcVelocity(snapshot);
    const distributionSkew = calcDistributionSkew(snapshot);
    
    const dataCompleteness = calcDataCompleteness(snapshot);
    const confidence = calcConfidence(snapshot, dataCompleteness);
    
    const drivers = generateDrivers(
      flowScore, exchangePressure, whaleActivity, 
      networkHeat, velocity, distributionSkew
    );
    
    return {
      symbol: snapshot.symbol,
      t0: snapshot.t0,
      window: snapshot.window,
      
      flowScore,
      exchangePressure,
      whaleActivity,
      networkHeat,
      velocity,
      distributionSkew,
      
      dataCompleteness,
      confidence,
      
      drivers,
      missing: snapshot.missingFields || [],
      
      rawScores: {
        flowRaw: snapshot.netFlowUsd,
        exchangeRaw: snapshot.exchangeNetUsd,
        whaleRaw: snapshot.largeTransfersVolumeUsd,
        heatRaw: snapshot.txCount,
        velocityRaw: Math.abs(snapshot.netInflowUsd) + Math.abs(snapshot.netOutflowUsd),
        skewRaw: snapshot.largeTransfersVolumeUsd / (Math.abs(snapshot.netFlowUsd) + 1),
      },
    };
  }
}

// Singleton instance
export const metricsEngine = new OnchainMetricsEngine();

console.log('[OnChain V2] Metrics Engine loaded');
