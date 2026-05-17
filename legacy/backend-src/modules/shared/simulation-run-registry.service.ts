/**
 * Simulation Run Registry Service
 * =================================
 * 
 * F5: Records simulation runs for reproducibility.
 * 
 * Features:
 * - Unique runId for each simulation
 * - Data/code fingerprints for reproducibility
 * - Progress tracking
 * - Result storage
 * - Evidence logging
 */

import crypto from 'crypto';
import { SimulationRunModel, SimulationRunDoc } from './simulation-run.model.js';
import { getEvidenceWriterService } from './evidence-writer.service.js';

export interface CreateRunInput {
  moduleKey: string;
  kind: string;
  window?: string;
  params: Record<string, any>;
  manifest: Record<string, any>;
  dataFingerprint: string;
  codeFingerprint: string;
}

export interface ResultSummary {
  returnPct?: number;
  maxDD?: number;
  sharpe?: number;
  winRate?: number;
  expectancy?: number;
  trades?: number;
  [key: string]: any;
}

export class SimulationRunRegistryService {
  /**
   * Generate SHA256 hash of object
   */
  sha256(obj: any): string {
    return crypto.createHash('sha256').update(JSON.stringify(obj)).digest('hex').slice(0, 16);
  }

  /**
   * Generate data fingerprint from dataset info
   */
  generateDataFingerprint(info: {
    moduleKey: string;
    window?: string;
    startDate?: Date;
    endDate?: Date;
    sampleCount: number;
    labelVersion?: number;
  }): string {
    return this.sha256({
      moduleKey: info.moduleKey,
      window: info.window,
      startDate: info.startDate?.toISOString(),
      endDate: info.endDate?.toISOString(),
      sampleCount: info.sampleCount,
      labelVersion: info.labelVersion,
    });
  }

  /**
   * Create new simulation run
   */
  async createRun(input: CreateRunInput): Promise<{ runId: string }> {
    const evidence = getEvidenceWriterService();
    const runId = crypto.randomUUID();

    await SimulationRunModel.create({
      runId,
      moduleKey: input.moduleKey,
      kind: input.kind,
      window: input.window,
      params: input.params,
      manifest: input.manifest,
      dataFingerprint: input.dataFingerprint,
      codeFingerprint: input.codeFingerprint,
      status: 'QUEUED',
      progress: { step: 0, total: 0, message: 'queued' },
    });

    await evidence.append(
      input.moduleKey as any,
      'simulation_run_recorded' as any,
      'INFO',
      `Simulation run created: ${input.kind}`,
      {},
      { runId, kind: input.kind, window: input.window }
    );

    console.log(`[SimRegistry] Created run ${runId} (${input.kind})`);

    return { runId };
  }

  /**
   * Start simulation run
   */
  async startRun(runId: string, totalSteps: number): Promise<void> {
    await SimulationRunModel.updateOne(
      { runId },
      {
        $set: {
          status: 'RUNNING',
          startedAt: new Date(),
          progress: { step: 0, total: totalSteps, message: 'running' },
        },
      }
    );

    const evidence = getEvidenceWriterService();
    await evidence.append(
      'shared',
      'simulation_run_recorded' as any,
      'INFO',
      `Simulation run started: ${runId}`,
      {},
      { runId, totalSteps }
    );
  }

  /**
   * Update progress
   */
  async updateProgress(runId: string, step: number, message: string): Promise<void> {
    await SimulationRunModel.updateOne(
      { runId },
      {
        $set: {
          'progress.step': step,
          'progress.message': message,
        },
      }
    );
  }

  /**
   * Finish simulation run with results
   */
  async finishRun(runId: string, resultSummary: ResultSummary, artifacts?: Record<string, any>): Promise<void> {
    await SimulationRunModel.updateOne(
      { runId },
      {
        $set: {
          status: 'DONE',
          finishedAt: new Date(),
          resultSummary,
          artifacts,
        },
      }
    );

    const evidence = getEvidenceWriterService();
    await evidence.append(
      'shared',
      'simulation_run_recorded' as any,
      'INFO',
      `Simulation run finished: ${runId}`,
      {},
      { runId, resultSummary }
    );

    console.log(`[SimRegistry] Finished run ${runId}`);
  }

  /**
   * Mark simulation run as failed
   */
  async failRun(runId: string, error: Error | string): Promise<void> {
    const errorObj = typeof error === 'string' ? { message: error } : { message: error.message, stack: error.stack };

    await SimulationRunModel.updateOne(
      { runId },
      {
        $set: {
          status: 'FAILED',
          finishedAt: new Date(),
          error: errorObj,
        },
      }
    );

    const evidence = getEvidenceWriterService();
    await evidence.append(
      'shared',
      'simulation_run_recorded' as any,
      'WARN',
      `Simulation run failed: ${runId}`,
      {},
      { runId, error: errorObj.message }
    );

    console.log(`[SimRegistry] Failed run ${runId}: ${errorObj.message}`);
  }

  /**
   * Get simulation run by ID
   */
  async getRun(runId: string): Promise<SimulationRunDoc | null> {
    return SimulationRunModel.findOne({ runId }).lean();
  }

  /**
   * List recent runs for a module
   */
  async listRuns(moduleKey: string, limit: number = 20): Promise<SimulationRunDoc[]> {
    return SimulationRunModel.find({ moduleKey })
      .sort({ createdAt: -1 })
      .limit(limit)
      .lean();
  }

  /**
   * Check if a similar run already exists (idempotency)
   */
  async findExistingRun(
    moduleKey: string,
    kind: string,
    dataFingerprint: string,
    codeFingerprint: string,
    paramsHash: string
  ): Promise<SimulationRunDoc | null> {
    // Find a DONE run with same fingerprints
    const runs = await SimulationRunModel.find({
      moduleKey,
      kind,
      dataFingerprint,
      codeFingerprint,
      status: 'DONE',
    }).lean();

    // Check params hash
    for (const run of runs) {
      if (this.sha256(run.params) === paramsHash) {
        return run;
      }
    }

    return null;
  }

  /**
   * Get run statistics
   */
  async getStats(moduleKey: string): Promise<{
    total: number;
    done: number;
    failed: number;
    running: number;
  }> {
    const [total, done, failed, running] = await Promise.all([
      SimulationRunModel.countDocuments({ moduleKey }),
      SimulationRunModel.countDocuments({ moduleKey, status: 'DONE' }),
      SimulationRunModel.countDocuments({ moduleKey, status: 'FAILED' }),
      SimulationRunModel.countDocuments({ moduleKey, status: 'RUNNING' }),
    ]);

    return { total, done, failed, running };
  }
}

// Singleton
let registryInstance: SimulationRunRegistryService | null = null;

export function getSimulationRunRegistryService(): SimulationRunRegistryService {
  if (!registryInstance) {
    registryInstance = new SimulationRunRegistryService();
  }
  return registryInstance;
}

console.log('[Shared] Simulation Run Registry Service loaded (F5)');
