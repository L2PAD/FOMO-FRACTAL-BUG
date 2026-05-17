/**
 * Labels Service
 * ===============
 * 
 * P0 Labeling: Resolve and manage entity labels
 */

import { AddressLabelModel, LabelType } from './addressLabel.model';

export interface AddressLabel {
  chainId: number;
  address: string;
  labelType: LabelType;
  entityId: string;
  name: string;
  tags: string[];
  confidence: number;
  source?: string;
}

export class LabelsService {
  /**
   * Resolve single address to label
   */
  async resolve(chainId: number, address: string): Promise<AddressLabel | null> {
    const addr = String(address).toLowerCase();
    return AddressLabelModel.findOne({ chainId, address: addr }).lean();
  }

  /**
   * Batch resolve addresses to labels
   */
  async batchResolve(chainId: number, addresses: string[]): Promise<Record<string, AddressLabel>> {
    const addrs = (addresses || []).map((a) => String(a).toLowerCase());
    if (!addrs.length) return {};

    const rows = await AddressLabelModel.find({ chainId, address: { $in: addrs } }).lean();
    const map: Record<string, AddressLabel> = {};
    rows.forEach((r: any) => (map[r.address] = r as AddressLabel));
    return map;
  }

  /**
   * Upsert multiple labels
   */
  async upsertMany(
    items: Array<
      Partial<AddressLabel> & {
        chainId: number;
        address: string;
        labelType: LabelType;
        entityId: string;
        name: string;
      }
    >
  ) {
    if (!items?.length) return { ok: true, upserted: 0 };

    const ops = items.map((it) => {
      const addr = String(it.address).toLowerCase();
      return {
        updateOne: {
          filter: { chainId: it.chainId, address: addr },
          update: {
            $set: {
              chainId: it.chainId,
              address: addr,
              labelType: it.labelType,
              entityId: it.entityId,
              name: it.name,
              tags: it.tags ?? [],
              source: it.source ?? 'seed',
              confidence: typeof it.confidence === 'number' ? it.confidence : 0.85,
            },
          },
          upsert: true,
        },
      };
    });

    const r = await AddressLabelModel.bulkWrite(ops, { ordered: false });
    return { ok: true, upserted: (r.upsertedCount ?? 0) + (r.modifiedCount ?? 0) };
  }

  /**
   * List labels with filters
   */
  async list(params: { chainId: number; q?: string; type?: LabelType; limit?: number }) {
    const limit = Math.min(Math.max(params.limit ?? 50, 10), 200);
    const query: any = { chainId: params.chainId };

    if (params.type) query.labelType = params.type;

    if (params.q) {
      const q = String(params.q).trim();
      query.$or = [
        { address: q.toLowerCase() },
        { entityId: new RegExp(q, 'i') },
        { name: new RegExp(q, 'i') },
        { tags: new RegExp(q, 'i') },
      ];
    }

    const rows = await AddressLabelModel.find(query)
      .sort({ labelType: 1, name: 1 })
      .limit(limit)
      .lean();
    return { ok: true, items: rows };
  }

  /**
   * Get stats
   */
  async stats(chainId: number) {
    const counts = await AddressLabelModel.aggregate([
      { $match: { chainId } },
      { $group: { _id: '$labelType', count: { $sum: 1 } } },
    ]);

    const total = counts.reduce((acc: number, c: any) => acc + c.count, 0);
    const byType: Record<string, number> = {};
    counts.forEach((c: any) => (byType[c._id] = c.count));

    return { ok: true, chainId, total, byType };
  }
}
