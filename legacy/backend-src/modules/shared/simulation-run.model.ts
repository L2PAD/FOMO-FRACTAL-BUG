/**
 * Simulation Run Model
 * ======================
 * 
 * F5: Stores simulation runs for reproducibility and audit.
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export interface SimulationRunDoc extends Document {
  runId: string;
  moduleKey: string;          // "sentiment" | "exchange"
  kind: string;               // "WALK_FWD" | "GRID" | "MC" | "90D" | "180D"
  window?: string;            // "24H" | "7D" | "30D"

  params: Record<string, any>;
  manifest: Record<string, any>;

  dataFingerprint: string;
  codeFingerprint: string;

  status: string;             // "QUEUED" | "RUNNING" | "DONE" | "FAILED"
  progress: {
    step: number;
    total: number;
    message: string;
  };

  resultSummary?: {
    returnPct?: number;
    maxDD?: number;
    sharpe?: number;
    winRate?: number;
    expectancy?: number;
    trades?: number;
    [key: string]: any;
  };

  artifacts?: Record<string, any>;
  error?: Record<string, any>;

  createdAt: Date;
  startedAt?: Date;
  finishedAt?: Date;
}

const SimulationRunSchema = new Schema<SimulationRunDoc>(
  {
    runId: { type: String, required: true, unique: true, index: true },
    moduleKey: { type: String, required: true, index: true },
    kind: { type: String, required: true },
    window: { type: String },

    params: { type: Schema.Types.Mixed, required: true },
    manifest: { type: Schema.Types.Mixed, required: true },

    dataFingerprint: { type: String, required: true, index: true },
    codeFingerprint: { type: String, required: true },

    status: { type: String, required: true, index: true },
    progress: {
      step: { type: Number, default: 0 },
      total: { type: Number, default: 0 },
      message: { type: String, default: '' },
    },

    resultSummary: { type: Schema.Types.Mixed },
    artifacts: { type: Schema.Types.Mixed },
    error: { type: Schema.Types.Mixed },

    createdAt: { type: Date, default: () => new Date(), index: true },
    startedAt: { type: Date },
    finishedAt: { type: Date },
  },
  {
    timestamps: false,
    collection: 'ml_simulation_runs',
  }
);

SimulationRunSchema.index({ moduleKey: 1, dataFingerprint: 1, codeFingerprint: 1 });

export const SimulationRunModel: Model<SimulationRunDoc> =
  (mongoose.models.SimulationRun as Model<SimulationRunDoc>) ||
  mongoose.model<SimulationRunDoc>('SimulationRun', SimulationRunSchema);

console.log('[Shared] Simulation Run Model loaded (F5)');
