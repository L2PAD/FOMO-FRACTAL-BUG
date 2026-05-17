/**
 * Evidence Store Service
 * ========================
 * 
 * F2: Append-only event store for critical ML decisions.
 * 
 * Tracks:
 * - guard_state_changed
 * - training_blocked / training_started
 * - baseline_create_attempted / baseline_created
 * - promotion_attempted / promoted
 * - rollback_triggered
 * - freeze_blocked_action
 */

import mongoose, { Schema, Document, Model } from 'mongoose';

export type EvidenceModule = 'sentiment' | 'exchange' | 'shared';
export type EvidenceSeverity = 'INFO' | 'WARN' | 'CRITICAL';

export type EvidenceType =
  | 'guard_state_changed'
  | 'training_blocked'
  | 'training_started'
  | 'training_completed'
  | 'baseline_create_attempted'
  | 'baseline_created'
  | 'baseline_blocked'
  | 'promotion_attempted'
  | 'promoted'
  | 'promotion_blocked'
  | 'rollback_triggered'
  | 'rollback_completed'
  | 'freeze_blocked_action'
  | 'uri_level_changed'
  | 'drift_status_changed'
  | 'capital_alert'
  | 'parser_health_changed'
  | 'safe_mode_activated'
  | 'safe_mode_deactivated';

export interface EvidenceContext {
  manifestVersion?: string;
  uriScore?: number;
  uriLevel?: string;
  dataHealth?: number;
  driftHealth?: number;
  capitalHealth?: number;
  gates?: Record<string, boolean>;
  lockKey?: string;
  windowId?: string;
  runId?: string;
  horizon?: string;
  window?: string;
}

export interface EvidenceEventDoc extends Document {
  module: EvidenceModule;
  type: EvidenceType;
  severity: EvidenceSeverity;
  at: Date;
  context: EvidenceContext;
  payload: Record<string, any>;
  message: string;
}

const EvidenceEventSchema = new Schema<EvidenceEventDoc>(
  {
    module: { type: String, enum: ['sentiment', 'exchange', 'shared'], required: true, index: true },
    type: { type: String, required: true, index: true },
    severity: { type: String, enum: ['INFO', 'WARN', 'CRITICAL'], default: 'INFO' },
    at: { type: Date, default: Date.now, index: true },
    context: { type: Schema.Types.Mixed, default: {} },
    payload: { type: Schema.Types.Mixed, default: {} },
    message: { type: String, default: '' },
  },
  {
    timestamps: false,
    collection: 'ml_evidence_events',
  }
);

EvidenceEventSchema.index({ module: 1, type: 1, at: -1 });
EvidenceEventSchema.index({ module: 1, severity: 1, at: -1 });

export const EvidenceEventModel: Model<EvidenceEventDoc> =
  (mongoose.models.EvidenceEvent as Model<EvidenceEventDoc>) ||
  mongoose.model<EvidenceEventDoc>('EvidenceEvent', EvidenceEventSchema);

// Max payload size (10KB)
const MAX_PAYLOAD_SIZE = 10 * 1024;

export class EvidenceWriterService {
  /**
   * Append evidence event (fire-and-forget)
   */
  async append(
    module: EvidenceModule,
    type: EvidenceType,
    severity: EvidenceSeverity,
    message: string,
    context?: EvidenceContext,
    payload?: Record<string, any>
  ): Promise<void> {
    try {
      // Safe stringify with size limit
      let safePayload = payload || {};
      const payloadStr = JSON.stringify(safePayload);
      if (payloadStr.length > MAX_PAYLOAD_SIZE) {
        safePayload = { truncated: true, originalSize: payloadStr.length };
      }

      await EvidenceEventModel.create({
        module,
        type,
        severity,
        at: new Date(),
        context: context || {},
        payload: safePayload,
        message,
      });

      console.log(`[Evidence] ${severity} ${module}:${type} - ${message}`);
    } catch (err) {
      // Fire-and-forget: don't break caller
      console.error('[Evidence] Failed to write event:', err);
    }
  }

  /**
   * Get recent events for a module
   */
  async getRecent(
    module: EvidenceModule,
    options: {
      limit?: number;
      type?: EvidenceType;
      severity?: EvidenceSeverity;
      since?: Date;
    } = {}
  ): Promise<EvidenceEventDoc[]> {
    const { limit = 50, type, severity, since } = options;

    const query: any = { module };
    if (type) query.type = type;
    if (severity) query.severity = severity;
    if (since) query.at = { $gte: since };

    return EvidenceEventModel.find(query)
      .sort({ at: -1 })
      .limit(limit)
      .lean();
  }

  /**
   * Get event counts by type (last 24h)
   */
  async getStats(module: EvidenceModule): Promise<Record<string, number>> {
    const since = new Date(Date.now() - 24 * 3600_000);

    const pipeline = [
      { $match: { module, at: { $gte: since } } },
      { $group: { _id: '$type', count: { $sum: 1 } } },
    ];

    const results = await EvidenceEventModel.aggregate(pipeline);
    const stats: Record<string, number> = {};
    for (const r of results) {
      stats[r._id] = r.count;
    }
    return stats;
  }
}

// Singleton
let evidenceWriterInstance: EvidenceWriterService | null = null;

export function getEvidenceWriterService(): EvidenceWriterService {
  if (!evidenceWriterInstance) {
    evidenceWriterInstance = new EvidenceWriterService();
  }
  return evidenceWriterInstance;
}

console.log('[Shared] Evidence Writer Service loaded (F2)');
