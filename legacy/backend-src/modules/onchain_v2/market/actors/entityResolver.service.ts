/**
 * Entity Resolver Service
 * ========================
 * 
 * P0.6.1: Multi-layer entity resolution
 * 
 * Layers (in order of confidence):
 * 1. LABEL_V2 — v2 institutional labels (seed, highest accuracy)
 * 2. ENTITY_V1 — v1 entities addresses membership
 * 3. ACTOR_CLUSTER_V1 — v1 actor clustering (hypothesis)
 * 4. BEHAVIORAL_FALLBACK — heuristic inference
 */

import { LabelsService } from '../../labels/labels.service';
import { ResolvedEntity, EntityResolutionContext } from './entityResolution.types';

// V1 imports
import { EntityModel } from '../../../../core/entities/entities.model';
import { ActorModel } from '../../../../core/actors/actor.model';

export interface EntityResolverOptions {
  enableV1?: boolean;
}

export class EntityResolverService {
  constructor(
    private readonly labels: LabelsService,
    private readonly opts: EntityResolverOptions = { enableV1: true }
  ) {}

  /**
   * Resolve counterparty address to entity with attribution
   */
  async resolve(params: {
    chainId: number;
    counterparty: string;
    ctx?: EntityResolutionContext;
  }): Promise<ResolvedEntity> {
    const addr = String(params.counterparty || '').toLowerCase();
    const chainId = params.chainId;

    if (!addr || addr.length < 10) {
      return this.behavioralFallback(params.ctx);
    }

    // ═══════════════════════════════════════════════════════════════
    // LAYER 1: V2 Labels (Institutional, highest confidence)
    // ═══════════════════════════════════════════════════════════════
    try {
      const label = await this.labels.resolve(chainId, addr);
      if (label) {
        return {
          entityId: label.entityId,
          entityName: label.name || label.entityId,
          entityType: this.mapLabelTypeToEntityType(label.labelType),
          confidence: this.clamp01(label.confidence ?? 0.95),
          source: 'LABEL_V2',
          labelType: label.labelType,
          evidence: [{ 
            kind: 'label_v2', 
            value: { source: label.source, labelType: label.labelType, address: addr } 
          }],
        };
      }
    } catch (err) {
      // Continue to next layer
    }

    // Skip v1 layers if disabled
    if (!this.opts?.enableV1) {
      return this.behavioralFallback(params.ctx);
    }

    // ═══════════════════════════════════════════════════════════════
    // LAYER 2: V1 Entities membership (known organizations)
    // ═══════════════════════════════════════════════════════════════
    try {
      const v1Entity = await EntityModel.findOne({ 
        primaryAddresses: { $regex: new RegExp(`^${addr}$`, 'i') }
      })
        .select('slug name category coverage attribution')
        .lean();

      if (v1Entity) {
        return {
          entityId: String((v1Entity as any).slug || (v1Entity as any)._id),
          entityName: String((v1Entity as any).name || (v1Entity as any).slug),
          entityType: String((v1Entity as any).category || 'entity'),
          confidence: this.clamp01(((v1Entity as any).coverage ?? 80) / 100),
          source: 'ENTITY_V1',
          evidence: [{ 
            kind: 'entity_v1', 
            value: { 
              slug: (v1Entity as any).slug,
              attribution: (v1Entity as any).attribution,
              address: addr 
            } 
          }],
        };
      }
    } catch (err) {
      // Continue to next layer
    }

    // ═══════════════════════════════════════════════════════════════
    // LAYER 3: V1 Actor Clusters (inference/hypothesis)
    // ═══════════════════════════════════════════════════════════════
    try {
      const actor = await ActorModel.findOne({ 
        addresses: { $regex: new RegExp(`^${addr}$`, 'i') }
      })
        .select('id name type sourceLevel coverage')
        .lean();

      if (actor) {
        const actorDoc = actor as any;
        return {
          entityId: `actor:${String(actorDoc.id)}`,
          entityName: String(actorDoc.name || `Actor ${String(actorDoc.id).slice(0, 8)}`),
          entityType: String(actorDoc.type || 'actor'),
          confidence: this.clamp01((actorDoc.coverage?.score ?? 65) / 100),
          source: 'ACTOR_CLUSTER_V1',
          evidence: [{ 
            kind: 'actor_cluster', 
            value: { 
              actorId: actorDoc.id,
              sourceLevel: actorDoc.sourceLevel,
              address: addr 
            } 
          }],
        };
      }
    } catch (err) {
      // Continue to fallback
    }

    // ═══════════════════════════════════════════════════════════════
    // LAYER 4: Behavioral Fallback
    // ═══════════════════════════════════════════════════════════════
    return this.behavioralFallback(params.ctx);
  }

  /**
   * Batch resolve multiple addresses
   */
  async batchResolve(params: {
    chainId: number;
    counterparties: string[];
    ctx?: EntityResolutionContext;
  }): Promise<Map<string, ResolvedEntity>> {
    const results = new Map<string, ResolvedEntity>();
    
    // First, batch resolve v2 labels for efficiency
    const addrs = params.counterparties.map(a => String(a).toLowerCase()).filter(a => a.length >= 10);
    const labelMap = await this.labels.batchResolve(params.chainId, addrs);
    
    for (const addr of addrs) {
      if (labelMap[addr]) {
        const label = labelMap[addr];
        results.set(addr, {
          entityId: label.entityId,
          entityName: label.name || label.entityId,
          entityType: this.mapLabelTypeToEntityType(label.labelType),
          confidence: this.clamp01(label.confidence ?? 0.95),
          source: 'LABEL_V2',
          labelType: label.labelType,
          evidence: [{ kind: 'label_v2', value: { source: label.source } }],
        });
      }
    }
    
    // Resolve remaining addresses individually
    const unresolved = addrs.filter(a => !results.has(a));
    for (const addr of unresolved) {
      const resolved = await this.resolve({
        chainId: params.chainId,
        counterparty: addr,
        ctx: params.ctx,
      });
      results.set(addr, resolved);
    }
    
    return results;
  }

  /**
   * Behavioral fallback based on context
   */
  private behavioralFallback(ctx?: EntityResolutionContext): ResolvedEntity {
    const src = String(ctx?.source || 'unknown').toLowerCase();
    
    if (ctx?.isWhale) {
      return {
        entityId: 'whale:unknown',
        entityName: 'Whale (unknown)',
        entityType: 'whale',
        confidence: 0.35,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'isWhale=true' }],
      };
    }
    
    if (src === 'cex') {
      return {
        entityId: 'cex:unknown',
        entityName: 'CEX (unknown)',
        entityType: 'exchange',
        confidence: 0.35,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'source=cex' }],
      };
    }
    
    if (src === 'bridge') {
      return {
        entityId: 'bridge:unknown',
        entityName: 'Bridge (unknown)',
        entityType: 'bridge',
        confidence: 0.35,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'source=bridge' }],
      };
    }
    
    if (src === 'dex') {
      return {
        entityId: 'dex:market',
        entityName: 'DEX market',
        entityType: 'dex',
        confidence: 0.25,
        source: 'BEHAVIORAL_FALLBACK',
        evidence: [{ kind: 'heuristic', value: 'source=dex' }],
      };
    }
    
    return {
      entityId: 'unknown:address',
      entityName: 'Unknown',
      entityType: 'unknown',
      confidence: 0.15,
      source: 'BEHAVIORAL_FALLBACK',
      evidence: [{ kind: 'heuristic', value: 'fallback' }],
    };
  }

  /**
   * Map v2 label type to unified entity type
   */
  private mapLabelTypeToEntityType(labelType?: string): string {
    const type = String(labelType || '').toUpperCase();
    switch (type) {
      case 'EXCHANGE': return 'exchange';
      case 'BRIDGE': return 'bridge';
      case 'PROTOCOL': return 'protocol';
      case 'FUND': return 'fund';
      case 'WHALE': return 'whale';
      default: return 'unknown';
    }
  }

  /**
   * Clamp value to 0-1 range
   */
  private clamp01(x: number): number {
    if (!Number.isFinite(x)) return 0;
    return Math.max(0, Math.min(1, x));
  }
}
