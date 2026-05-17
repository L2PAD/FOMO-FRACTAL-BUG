/**
 * Sentiment Simulation Capital Engine
 * =====================================
 * 
 * BLOCK 7: Tracks capital, equity curve, MaxDD during simulation.
 */

export class SentimentSimCapital {
  private capital: number;
  private peak: number;
  private maxDD: number = 0;
  private equityCurve: Array<{ date: Date; equity: number }> = [];

  constructor(startCapital: number = 1.0) {
    this.capital = startCapital;
    this.peak = startCapital;
  }

  /**
   * Apply return and update tracking
   */
  applyReturn(ret: number, date: Date): void {
    this.capital *= (1 + ret);
    this.peak = Math.max(this.peak, this.capital);

    const dd = (this.peak - this.capital) / this.peak;
    this.maxDD = Math.max(this.maxDD, dd);

    this.equityCurve.push({ date, equity: this.capital });
  }

  getCapital(): number {
    return this.capital;
  }

  getMaxDD(): number {
    return this.maxDD;
  }

  getEquityCurve(): Array<{ date: Date; equity: number }> {
    return this.equityCurve;
  }

  getTotalReturnPct(): number {
    return this.capital - 1;
  }
}

console.log('[Sentiment-ML] Simulation Capital Engine loaded (BLOCK 7)');
