/**
 * Forecast Evolution Service
 * Shows how the model changed opinion over time (target evolution).
 * Calculates Model Drift = stddev(last N targets).
 * Separate from chart-v3 — reads same collection, different perspective.
 */

interface EvolutionPoint {
  date: number;       // unix seconds
  dateBucket: string; // YYYY-MM-DD
  target: number;
  entry: number;
  confidence: number;
  direction: string;
  runId: string;
}

interface DriftResult {
  value: number;
  status: 'stable' | 'moderate' | 'unstable';
  windowDays: number;
}

interface EvolutionResponse {
  ok: boolean;
  asset: string;
  horizonDays: number;
  points: EvolutionPoint[];
  drift: DriftResult;
  trend: { direction: 'bullish' | 'bearish' | 'sideways'; changePct: number };
  source: string;
}

export class ForecastEvolutionService {
  private static instance: ForecastEvolutionService;

  static getInstance(): ForecastEvolutionService {
    if (!this.instance) this.instance = new ForecastEvolutionService();
    return this.instance;
  }

  async getEvolution(asset: string, horizonDays: number): Promise<EvolutionResponse> {
    const { getDb } = await import('../../../db/mongodb.js');
    const db = getDb();

    // Use aggregation to deduplicate by runId — keep the latest record per run
    const forecasts = await db.collection('exchange_forecasts')
      .aggregate([
        { $match: { asset: asset.toUpperCase(), horizonDays } },
        { $sort: { createdAt: -1 } },
        // Group by runId, take the first (latest) record per run
        { $group: {
          _id: '$runId',
          createdAt: { $first: '$createdAt' },
          createdBucket: { $first: '$createdBucket' },
          targetPrice: { $first: '$targetPrice' },
          entryPrice: { $first: '$entryPrice' },
          confidence: { $first: '$confidence' },
          direction: { $first: '$direction' },
          runId: { $first: '$runId' },
        }},
        { $sort: { createdAt: 1 } },
        { $limit: 180 },
      ])
      .toArray();

    const points: EvolutionPoint[] = forecasts.map((f: any) => {
      const createdMs = f.createdAt > 1e12 ? f.createdAt : f.createdAt * 1000;
      return {
        date: Math.floor(createdMs / 1000),
        dateBucket: f.createdBucket || '',
        target: f.targetPrice,
        entry: f.entryPrice || 0,
        confidence: f.confidence || 0,
        direction: f.direction || 'NEUTRAL',
        runId: f.runId || '',
      };
    });

    // Drift: stddev of last 7 targets
    const driftWindow = 7;
    const drift = this.calculateDrift(points, driftWindow);

    // Trend: compare last target to target N days ago
    const trend = this.calculateTrend(points);

    return {
      ok: true,
      asset: asset.toUpperCase(),
      horizonDays,
      points,
      drift,
      trend,
      source: 'db',
    };
  }

  private calculateDrift(points: EvolutionPoint[], windowDays: number): DriftResult {
    const last = points.slice(-windowDays);
    if (last.length < 2) {
      return { value: 0, status: 'stable', windowDays };
    }

    const values = last.map(p => p.target);
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    const variance = values.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / values.length;
    const stddev = Math.sqrt(variance);

    let status: 'stable' | 'moderate' | 'unstable';
    if (stddev < 1000) status = 'stable';
    else if (stddev < 3000) status = 'moderate';
    else status = 'unstable';

    return { value: Math.round(stddev), status, windowDays };
  }

  private calculateTrend(points: EvolutionPoint[]): { direction: 'bullish' | 'bearish' | 'sideways'; changePct: number } {
    if (points.length < 3) {
      return { direction: 'sideways', changePct: 0 };
    }

    const recent = points[points.length - 1].target;
    const lookback = points[Math.max(0, points.length - 7)].target;
    const changePct = ((recent - lookback) / lookback) * 100;

    let direction: 'bullish' | 'bearish' | 'sideways';
    if (changePct > 1) direction = 'bullish';
    else if (changePct < -1) direction = 'bearish';
    else direction = 'sideways';

    return { direction, changePct: Math.round(changePct * 100) / 100 };
  }
}
