/**
 * Wallet Snapshot Cache Model — Phase C4
 * ========================================
 * Pre-computed wallet profiles cached in MongoDB.
 * Avoids expensive on-demand computation for frequently viewed addresses.
 */

import mongoose, { Schema } from 'mongoose';

const WalletSnapshotSchema = new Schema(
  {
    chainId:    { type: Number, required: true },
    address:    { type: String, required: true },
    window:     { type: String, required: true },  // '24h' | '7d' | '30d'

    snapshot:   { type: Schema.Types.Mixed, required: true },  // WalletProfileSnapshot

    computedAt: { type: Date, required: true },
    expiresAt:  { type: Date, required: true },
    source:     { type: String, default: 'job' },  // 'job' | 'on-demand'
  },
  { timestamps: false }
);

WalletSnapshotSchema.index(
  { chainId: 1, address: 1, window: 1 },
  { unique: true, name: 'uniq_wallet_snapshot' }
);

WalletSnapshotSchema.index(
  { expiresAt: 1 },
  { expireAfterSeconds: 0, name: 'ttl_snapshot' }
);

export const WalletSnapshotModel =
  mongoose.models.WalletSnapshot ||
  mongoose.model('WalletSnapshot', WalletSnapshotSchema, 'wallet_snapshots');
