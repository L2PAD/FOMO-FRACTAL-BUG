/**
 * Simulation Reporter
 * ===================
 * 
 * Generates JSON and CSV reports from simulation results.
 */

import { Db } from 'mongodb';
import { SimReport, SimIssue } from '../exchange_sim.types.js';
import * as fs from 'fs';
import * as path from 'path';

const REPORTS_COLLECTION = 'sim_reports';

export class SimReporter {
  constructor(private db: Db) {}
  
  /**
   * Save report to database
   */
  async saveToDb(report: SimReport): Promise<string> {
    const doc = {
      ...report,
      savedAt: new Date(),
    };
    
    const result = await this.db.collection(REPORTS_COLLECTION).insertOne(doc);
    return result.insertedId.toString();
  }
  
  /**
   * Export report as JSON file
   */
  async exportJson(report: SimReport, outputPath: string): Promise<void> {
    const json = JSON.stringify(report, null, 2);
    await fs.promises.writeFile(outputPath, json, 'utf-8');
    console.log(`[SimReporter] JSON report saved to ${outputPath}`);
  }
  
  /**
   * Export daily metrics as CSV
   */
  async exportDailyCsv(report: SimReport, outputPath: string): Promise<void> {
    const headers = ['date', 'wins', 'losses', 'winRate', 'retrains', 'promotions', 'rollbacks', 'avgConfidence'];
    const rows = report.dailyMetrics.map(d => {
      const total = d.wins + d.losses;
      const winRate = total > 0 ? (d.wins / total * 100).toFixed(2) : '0.00';
      return [
        d.date,
        d.wins,
        d.losses,
        winRate,
        d.retrains,
        d.promotions,
        d.rollbacks,
        d.avgConfidence.toFixed(4),
      ].join(',');
    });
    
    const csv = [headers.join(','), ...rows].join('\n');
    await fs.promises.writeFile(outputPath, csv, 'utf-8');
    console.log(`[SimReporter] Daily CSV saved to ${outputPath}`);
  }
  
  /**
   * Export symbol metrics as CSV
   */
  async exportSymbolCsv(report: SimReport, outputPath: string): Promise<void> {
    const headers = ['symbol', 'accuracy1D', 'accuracy7D', 'accuracy30D', 'retrains', 'promotions', 'rollbacks'];
    const rows = Object.entries(report.symbolMetrics).map(([symbol, m]) => {
      return [
        symbol,
        (m.accuracy1D * 100).toFixed(2),
        (m.accuracy7D * 100).toFixed(2),
        (m.accuracy30D * 100).toFixed(2),
        m.retrains,
        m.promotions,
        m.rollbacks,
      ].join(',');
    });
    
    const csv = [headers.join(','), ...rows].join('\n');
    await fs.promises.writeFile(outputPath, csv, 'utf-8');
    console.log(`[SimReporter] Symbol CSV saved to ${outputPath}`);
  }
  
  /**
   * Generate summary text
   */
  generateSummary(report: SimReport): string {
    const m = report.metrics;
    const lines: string[] = [];
    
    lines.push('═══════════════════════════════════════════════════════════════');
    lines.push('          EXCHANGE ML DIAGNOSTIC SIMULATION REPORT');
    lines.push('═══════════════════════════════════════════════════════════════');
    lines.push('');
    
    // Diagnostic mode info
    if (report.diagnosticMode) {
      lines.push(`MODE: ${report.diagnosticMode.toUpperCase()}`);
      if (report.gates) {
        lines.push(`Gates: retrain=${report.gates.retrain} shadow=${report.gates.shadow} promo=${report.gates.promotion} rollback=${report.gates.rollback} bias=${report.gates.bias}`);
      }
      lines.push('');
    }
    
    lines.push(`Status: ${report.status}`);
    lines.push(`Duration: ${((report.completedAt.getTime() - report.startedAt.getTime()) / 1000).toFixed(1)}s`);
    lines.push(`Days Simulated: ${m.totalDays}`);
    lines.push(`Symbols: ${m.totalSymbols}`);
    lines.push(`Total Predictions: ${m.totalPredictions}`);
    lines.push(`Total Outcomes: ${m.totalOutcomes}`);
    lines.push('');
    
    lines.push('─── ACCURACY BY HORIZON ───');
    lines.push(`  1D:  ${(m.accuracy['1D'].rate * 100).toFixed(2)}% (${m.accuracy['1D'].wins}W/${m.accuracy['1D'].losses}L)`);
    lines.push(`  7D:  ${(m.accuracy['7D'].rate * 100).toFixed(2)}% (${m.accuracy['7D'].wins}W/${m.accuracy['7D'].losses}L)`);
    lines.push(`  30D: ${(m.accuracy['30D'].rate * 100).toFixed(2)}% (${m.accuracy['30D'].wins}W/${m.accuracy['30D'].losses}L)`);
    lines.push('');
    
    lines.push('─── LIFECYCLE STABILITY ───');
    lines.push(`  Retrains: ${m.lifecycle.retrainCount}`);
    lines.push(`  Promotions: ${m.lifecycle.promotionCount}`);
    lines.push(`  Rollbacks: ${m.lifecycle.rollbackCount}`);
    lines.push(`  Throttled Retrains: ${m.lifecycle.throttledRetrains}`);
    lines.push(`  Guardrail Triggers: ${m.lifecycle.guardrailTriggers}`);
    lines.push(`  Drift Warnings: ${m.lifecycle.driftWarnings}`);
    lines.push(`  Drift Criticals: ${m.lifecycle.driftCriticals}`);
    lines.push('');
    
    lines.push('─── SHADOW COMPARISON ───');
    lines.push(`  Shadow Wins: ${m.shadow.shadowWins}`);
    lines.push(`  Active Wins: ${m.shadow.activeWins}`);
    const shadowRatio = m.shadow.shadowWins + m.shadow.activeWins > 0
      ? (m.shadow.shadowWins / (m.shadow.shadowWins + m.shadow.activeWins) * 100).toFixed(1)
      : '0.0';
    lines.push(`  Shadow Win Rate: ${shadowRatio}%`);
    lines.push('');
    
    lines.push('─── CROSS-HORIZON BIAS ───');
    lines.push(`  Bias Updates: ${m.bias.biasUpdates}`);
    lines.push(`  Avg 1D→7D Influence: ${(m.bias.avg1Dto7DInfluence * 100).toFixed(2)}%`);
    lines.push(`  Avg 7D→30D Influence: ${(m.bias.avg7Dto30DInfluence * 100).toFixed(2)}%`);
    lines.push(`  Max Influence Applied: ${(m.bias.maxInfluenceApplied * 100).toFixed(2)}%`);
    lines.push('');
    
    lines.push('─── STRESS METRICS ───');
    lines.push(`  Max Consecutive Promotions: ${m.stress.maxConsecutivePromotions}`);
    lines.push(`  Max Consecutive Rollbacks: ${m.stress.maxConsecutiveRollbacks}`);
    lines.push(`  Max Retrains/Week: ${m.stress.maxRetrainsPerWeek}`);
    lines.push(`  Confidence Volatility: ${(m.stress.confidenceVolatility * 100).toFixed(2)}%`);
    lines.push('');
    
    if (report.issues.length > 0) {
      lines.push('─── ISSUES DETECTED ───');
      for (const issue of report.issues) {
        lines.push(`  [${issue.severity}] ${issue.category}: ${issue.description}`);
        lines.push(`         Metric: ${issue.metric} = ${issue.value} (threshold: ${issue.threshold})`);
      }
      lines.push('');
    }
    
    if (report.recommendations.length > 0) {
      lines.push('─── RECOMMENDATIONS ───');
      for (const rec of report.recommendations) {
        lines.push(`  • ${rec}`);
      }
      lines.push('');
    }
    
    lines.push('═══════════════════════════════════════════════════════════════');
    
    return lines.join('\n');
  }
  
  /**
   * Print summary to console
   */
  printSummary(report: SimReport): void {
    console.log(this.generateSummary(report));
  }
  
  /**
   * Get historical reports from database
   */
  async getReports(limit: number = 10): Promise<SimReport[]> {
    const docs = await this.db
      .collection(REPORTS_COLLECTION)
      .find({})
      .sort({ startedAt: -1 })
      .limit(limit)
      .toArray();
    
    return docs as unknown as SimReport[];
  }
}

export function createSimReporter(db: Db): SimReporter {
  return new SimReporter(db);
}
