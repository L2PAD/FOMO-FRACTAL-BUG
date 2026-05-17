/**
 * Exchange Entity Model — Phase A1.2
 * ====================================
 *
 * Top-level entity for CEX exchanges.
 * Each exchange has many addresses (via AddressLabelModel).
 */

import mongoose, { Schema, Document, model } from 'mongoose';

export interface IExchangeEntity extends Document {
  entityId: string;
  entityName: string;
  entityType: 'cex';
  chains: number[];
  addressCount: number;
  status: 'active' | 'inactive';
  createdAt: Date;
  updatedAt: Date;
}

const ExchangeEntitySchema = new Schema<IExchangeEntity>({
  entityId:     { type: String, required: true, unique: true, index: true },
  entityName:   { type: String, required: true },
  entityType:   { type: String, default: 'cex' },
  chains:       { type: [Number], default: [1] },
  addressCount: { type: Number, default: 0 },
  status:       { type: String, default: 'active', enum: ['active', 'inactive'] },
}, {
  timestamps: true,
  collection: 'cex_entities',
});

export const ExchangeEntityModel = mongoose.models['ExchangeEntity'] as mongoose.Model<IExchangeEntity>
  || model<IExchangeEntity>('ExchangeEntity', ExchangeEntitySchema, 'cex_entities');
