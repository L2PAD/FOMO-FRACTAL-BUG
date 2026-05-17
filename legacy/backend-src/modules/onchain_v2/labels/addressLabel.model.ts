/**
 * Address Label Model
 * ====================
 * 
 * P0 Labeling: Entity classification for on-chain addresses
 */

import mongoose, { Schema, model } from 'mongoose';

export type LabelType =
  | 'EXCHANGE'
  | 'BRIDGE'
  | 'FUND'
  | 'SMART_MONEY'
  | 'WHALE'
  | 'PROTOCOL'
  | 'UNKNOWN';

const AddressLabelSchema = new Schema(
  {
    chainId: { type: Number, index: true, required: true },
    address: { type: String, index: true, required: true }, // lowercased
    labelType: {
      type: String,
      enum: ['EXCHANGE', 'BRIDGE', 'FUND', 'SMART_MONEY', 'WHALE', 'PROTOCOL', 'UNKNOWN'],
      index: true,
      required: true,
    },
    entityId: { type: String, index: true, required: true }, // binance/coinbase/op-bridge etc
    name: { type: String, required: true },
    tags: { type: [String], default: [] }, // ["hot","deposit","l1","l2"]
    source: { type: String, default: 'seed' }, // seed/manual/import
    confidence: { type: Number, default: 0.85 }, // 0..1
    // Phase A1.2 extensions
    addressType: {
      type: String,
      enum: ['hot_wallet', 'cold_wallet', 'sweep', 'deposit', 'withdrawal', 'treasury', null],
      index: true,
      default: null,
    },
    clusterId: { type: String, default: null }, // default = entityId
    isInternal: { type: Boolean, default: false },
    firstSeenAt: { type: Date, default: null },
    lastSeenAt: { type: Date, default: null },
  },
  { timestamps: true }
);

AddressLabelSchema.index({ chainId: 1, address: 1 }, { unique: true });

export const AddressLabelModel =
  mongoose.models.AddressLabel || model('AddressLabel', AddressLabelSchema, 'onchain_v2_address_labels');
