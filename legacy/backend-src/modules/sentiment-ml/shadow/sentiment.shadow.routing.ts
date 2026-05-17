/**
 * Shadow Decision Routing Engine
 * ================================
 * 
 * Context-aware ML/Rule routing based on proven edge.
 * 
 * RULES:
 * - Routing is DISABLED by default
 * - Only enable after First Read confirms ML edge in specific slices
 * - Each rule requires minSampleSize and minDelta validation
 * - Default action: RULE (safe fallback)
 */

import mongoose from 'mongoose';

// ── Types ──

export interface RoutingConditions {
  importance?: string[];     // e.g. ['high']
  recency?: string[];        // e.g. ['<1h', '1-3h']
  eventType?: string[];      // e.g. ['regulation', 'macro']
  assetClass?: string[];     // e.g. ['BTC', 'ETH']
  volatilityBucket?: string[]; // e.g. ['MED']
}

export interface RoutingRule {
  name: string;
  conditions: RoutingConditions;
  action: 'ML' | 'RULE';
  priority: number;          // higher = checked first
  enabled: boolean;
  
  // Validation guards
  minSampleSize: number;     // don't activate on noise (default: 20)
  minDelta: number;          // ML must be +X% better (default: 0.05)
  
  // Evidence (filled from analysis)
  evidence?: {
    samples: number;
    mlAccuracy: number;
    ruleAccuracy: number;
    delta: number;
    lastVerified?: string;   // ISO date
  };
}

// ── Mongoose Schema ──

const routingRuleSchema = new mongoose.Schema({
  name: { type: String, required: true, unique: true },
  conditions: {
    importance: [String],
    recency: [String],
    eventType: [String],
    assetClass: [String],
    volatilityBucket: [String],
  },
  action: { type: String, enum: ['ML', 'RULE'], required: true },
  priority: { type: Number, default: 0 },
  enabled: { type: Boolean, default: false },
  minSampleSize: { type: Number, default: 20 },
  minDelta: { type: Number, default: 0.05 },
  evidence: {
    samples: Number,
    mlAccuracy: Number,
    ruleAccuracy: Number,
    delta: Number,
    lastVerified: String,
  },
}, { timestamps: true });

let RoutingRuleModel: mongoose.Model<any> | null = null;

function getRoutingRuleModel() {
  if (!RoutingRuleModel) {
    RoutingRuleModel = mongoose.model('ShadowRoutingRule', routingRuleSchema);
  }
  return RoutingRuleModel;
}

// ── Routing Engine ──

export class ShadowRoutingEngine {
  private static DEFAULT_RULES: RoutingRule[] = [
    {
      name: 'high_priority_fresh',
      conditions: {
        importance: ['high'],
        recency: ['<1h', '1-3h'],
        eventType: ['regulation', 'macro'],
      },
      action: 'ML',
      priority: 100,
      enabled: false,
      minSampleSize: 20,
      minDelta: 0.05,
    },
    {
      name: 'high_importance_any',
      conditions: {
        importance: ['high'],
      },
      action: 'ML',
      priority: 50,
      enabled: false,
      minSampleSize: 20,
      minDelta: 0.05,
    },
    {
      name: 'default',
      conditions: {},
      action: 'RULE',
      priority: 0,
      enabled: true,
      minSampleSize: 0,
      minDelta: 0,
    },
  ];

  /**
   * Initialize default rules in DB (idempotent).
   */
  async seedDefaults(): Promise<{ seeded: number; existing: number }> {
    const Model = getRoutingRuleModel();
    let seeded = 0;
    let existing = 0;

    for (const rule of ShadowRoutingEngine.DEFAULT_RULES) {
      const exists = await Model.findOne({ name: rule.name });
      if (!exists) {
        await Model.create(rule);
        seeded++;
      } else {
        existing++;
      }
    }

    return { seeded, existing };
  }

  /**
   * Get all routing rules sorted by priority (desc).
   */
  async getRules(): Promise<RoutingRule[]> {
    const Model = getRoutingRuleModel();
    return Model.find().sort({ priority: -1 }).lean();
  }

  /**
   * Match context against rules. Returns first matching rule's action.
   * Rules checked in priority order (highest first).
   * Default: 'RULE'
   */
  async matchAction(context: {
    importance?: string;
    recency?: string;
    eventType?: string;
    assetClass?: string;
    volatilityBucket?: string;
  }): Promise<{ action: 'ML' | 'RULE'; matchedRule: string }> {
    const rules = await this.getRules();

    for (const rule of rules) {
      if (!rule.enabled) continue;

      const conds = rule.conditions || {};
      let matches = true;

      if (conds.importance?.length && context.importance) {
        if (!conds.importance.includes(context.importance)) matches = false;
      }
      if (conds.recency?.length && context.recency) {
        if (!conds.recency.includes(context.recency)) matches = false;
      }
      if (conds.eventType?.length && context.eventType) {
        if (!conds.eventType.includes(context.eventType)) matches = false;
      }
      if (conds.assetClass?.length && context.assetClass) {
        if (!conds.assetClass.includes(context.assetClass)) matches = false;
      }
      if (conds.volatilityBucket?.length && context.volatilityBucket) {
        if (!conds.volatilityBucket.includes(context.volatilityBucket)) matches = false;
      }

      if (matches) {
        return { action: rule.action, matchedRule: rule.name };
      }
    }

    return { action: 'RULE', matchedRule: 'default' };
  }

  /**
   * Update rule (enable/disable, change conditions, update evidence).
   */
  async updateRule(name: string, update: Partial<RoutingRule>): Promise<RoutingRule | null> {
    const Model = getRoutingRuleModel();
    return Model.findOneAndUpdate(
      { name },
      { $set: update },
      { new: true, lean: true },
    );
  }

  /**
   * Validate if a rule's evidence meets its guards.
   */
  validateEvidence(rule: RoutingRule): {
    valid: boolean;
    blockers: string[];
  } {
    const blockers: string[] = [];
    const ev = rule.evidence;

    if (!ev) {
      blockers.push('No evidence data');
      return { valid: false, blockers };
    }

    if (ev.samples < rule.minSampleSize) {
      blockers.push(`Samples ${ev.samples} < min ${rule.minSampleSize}`);
    }
    if (ev.delta < rule.minDelta) {
      blockers.push(`Delta ${(ev.delta * 100).toFixed(1)}% < min ${(rule.minDelta * 100).toFixed(0)}%`);
    }

    return { valid: blockers.length === 0, blockers };
  }
}

// Singleton
let routingInstance: ShadowRoutingEngine | null = null;

export function getShadowRoutingEngine(): ShadowRoutingEngine {
  if (!routingInstance) {
    routingInstance = new ShadowRoutingEngine();
  }
  return routingInstance;
}

console.log('[Sentiment-ML] Shadow Routing Engine loaded');
