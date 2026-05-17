/**
 * CEX Registry Service — Phase A1.2
 * ====================================
 *
 * Industrial-grade CEX address management:
 * - Bulk import with upsert (no duplicates)
 * - Auto-create exchange entity
 * - Recalculate address counts
 * - Registry stats
 */

import { ExchangeEntityModel } from './exchange_entity.model';
import { AddressLabelModel } from '../labels/addressLabel.model';

export interface ImportAddress {
  address: string;
  addressType?: string;
  confidence?: number;
  tags?: string[];
}

export interface ImportRequest {
  entityId: string;
  entityName: string;
  chainId: number;
  addresses: ImportAddress[];
}

export interface ImportReport {
  entityId: string;
  inserted: number;
  updated: number;
  total: number;
  errors: string[];
}

export class CexRegistryService {
  /**
   * Bulk import addresses for a CEX exchange
   */
  async bulkImport(req: ImportRequest): Promise<ImportReport> {
    const { entityId, entityName, chainId, addresses } = req;
    const errors: string[] = [];

    // 1. Upsert exchange entity
    await ExchangeEntityModel.findOneAndUpdate(
      { entityId },
      {
        $set: {
          entityName,
          entityType: 'cex',
          status: 'active',
          updatedAt: new Date(),
        },
        $addToSet: { chains: chainId },
        $setOnInsert: { createdAt: new Date() },
      },
      { upsert: true },
    );

    // 2. Bulk upsert addresses
    const ops = addresses
      .filter(a => {
        if (!a.address || !/^0x[a-fA-F0-9]{40}$/.test(a.address)) {
          errors.push(`Invalid address: ${a.address}`);
          return false;
        }
        return true;
      })
      .map(a => ({
        updateOne: {
          filter: {
            chainId,
            address: a.address.toLowerCase(),
          },
          update: {
            $set: {
              labelType: 'EXCHANGE',
              entityId,
              name: `${entityName} ${a.addressType || 'wallet'}`,
              addressType: a.addressType || 'hot_wallet',
              clusterId: entityId,
              confidence: a.confidence ?? 0.95,
              source: 'cex_registry',
              tags: a.tags || [entityId, 'cex', a.addressType || 'hot'],
              lastSeenAt: new Date(),
            },
            $setOnInsert: {
              firstSeenAt: new Date(),
            },
          },
          upsert: true,
        },
      }));

    let inserted = 0;
    let updated = 0;

    if (ops.length > 0) {
      const result = await AddressLabelModel.bulkWrite(ops, { ordered: false });
      inserted = result.upsertedCount || 0;
      updated = result.modifiedCount || 0;
    }

    // 3. Recalculate address count
    await this.recalcAddressCount(entityId, chainId);

    return {
      entityId,
      inserted,
      updated,
      total: ops.length,
      errors,
    };
  }

  /**
   * Recalculate address count for an exchange
   */
  async recalcAddressCount(entityId: string, chainId?: number): Promise<number> {
    const filter: any = { entityId, labelType: 'EXCHANGE' };
    if (chainId) filter.chainId = chainId;

    const count = await AddressLabelModel.countDocuments(filter);
    await ExchangeEntityModel.findOneAndUpdate(
      { entityId },
      { $set: { addressCount: count } },
    );
    return count;
  }

  /**
   * Get comprehensive registry stats
   */
  async getStats(chainId?: number): Promise<{
    exchangesCount: number;
    totalAddresses: number;
    byExchange: Array<{ entityId: string; entityName: string; count: number; status: string }>;
    byType: Array<{ addressType: string; count: number }>;
    chainsCovered: number[];
  }> {
    const labelFilter: any = { labelType: 'EXCHANGE' };
    if (chainId) labelFilter.chainId = chainId;

    // By exchange
    const byExchangeAgg = await AddressLabelModel.aggregate([
      { $match: labelFilter },
      { $group: { _id: '$entityId', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
    ]);

    // Get entity names
    const entities = await ExchangeEntityModel.find({}).lean();
    const entityMap = new Map(entities.map((e: any) => [e.entityId, e]));

    const byExchange = byExchangeAgg.map((r: any) => {
      const ent = entityMap.get(r._id);
      return {
        entityId: r._id,
        entityName: ent?.entityName || r._id,
        count: r.count,
        status: ent?.status || 'unknown',
      };
    });

    // By address type
    const byTypeAgg = await AddressLabelModel.aggregate([
      { $match: labelFilter },
      { $group: { _id: '$addressType', count: { $sum: 1 } } },
      { $sort: { count: -1 } },
    ]);
    const byType = byTypeAgg.map((r: any) => ({
      addressType: r._id || 'unknown',
      count: r.count,
    }));

    // Chains
    const chainsAgg = await AddressLabelModel.aggregate([
      { $match: { labelType: 'EXCHANGE' } },
      { $group: { _id: '$chainId' } },
    ]);

    return {
      exchangesCount: byExchange.length,
      totalAddresses: byExchange.reduce((s, e) => s + e.count, 0),
      byExchange,
      byType,
      chainsCovered: chainsAgg.map((r: any) => r._id),
    };
  }

  /**
   * List all exchanges
   */
  async listExchanges(): Promise<Array<{ entityId: string; entityName: string; addressCount: number; status: string }>> {
    const entities = await ExchangeEntityModel.find({ status: 'active' }).lean();
    return entities.map((e: any) => ({
      entityId: e.entityId,
      entityName: e.entityName,
      addressCount: e.addressCount,
      status: e.status,
    }));
  }
}
