/**
 * Backtest Run Model — Phase BT
 * ===============================
 * Stores backtest run results for audit and comparison.
 */

import mongoose, { Schema } from 'mongoose';

const BacktestRunSchema = new Schema(
  {
    chainId:   { type: Number, required: true },
    from:      { type: String, required: true },
    to:        { type: String, required: true },
    stepDays:  { type: Number, required: true },
    window:    { type: String, required: true },
    topK:      { type: Number, required: true },
    mode:      { type: String, required: true },
    horizons:  { type: [Number], required: true },

    points:          { type: Number },
    actionableRate:  { type: Number },
    coverage:        { type: Number },
    byH:             { type: Schema.Types.Mixed },
    dataWarning:     { type: String, default: null },
    elapsed:         { type: Number },
  },
  {
    collection: 'engine_backtest_runs',
    timestamps: true,
  }
);

BacktestRunSchema.index({ chainId: 1, createdAt: -1 });

export const BacktestRunModel =
  mongoose.models.BacktestRun ||
  mongoose.model('BacktestRun', BacktestRunSchema, 'engine_backtest_runs');
