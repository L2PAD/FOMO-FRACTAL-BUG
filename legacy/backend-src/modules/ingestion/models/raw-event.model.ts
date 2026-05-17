/**
 * RawEvent Mongoose Model
 * =======================
 * Source-agnostic storage for all ingested text events.
 * Collection: raw_events
 */

import mongoose, { Schema, Document } from 'mongoose';

export interface IRawEvent extends Document {
  externalId: string;
  sourceType: string;
  sourceName: string;

  text: string;
  title?: string;
  summary?: string;
  url?: string;

  publishedAt: Date;
  ingestedAt: Date;

  author?: {
    id?: string;
    handle?: string;
    name?: string;
    followers?: number;
    verified?: boolean;
  };

  publisher?: {
    name?: string;
    domain?: string;
  };

  engagement?: {
    likes?: number;
    reposts?: number;
    replies?: number;
    views?: number;
  };

  assetMentions?: string[];
  projectMentions?: string[];

  dedupeKey: string;
  raw: Record<string, any>;

  processed: boolean;
  processedAt?: Date;
}

const RawEventSchema = new Schema<IRawEvent>(
  {
    externalId: { type: String, required: true },
    sourceType: { type: String, required: true },
    sourceName: { type: String, required: true },

    text: { type: String, default: '' },
    title: String,
    summary: String,
    url: String,

    publishedAt: { type: Date, required: true },
    ingestedAt: { type: Date, required: true },

    author: {
      id: String,
      handle: String,
      name: String,
      followers: Number,
      verified: Boolean,
    },

    publisher: {
      name: String,
      domain: String,
    },

    engagement: {
      likes: Number,
      reposts: Number,
      replies: Number,
      views: Number,
    },

    assetMentions: [String],
    projectMentions: [String],

    dedupeKey: { type: String, required: true },
    raw: { type: Schema.Types.Mixed, default: {} },

    processed: { type: Boolean, default: false },
    processedAt: Date,
  },
  {
    timestamps: true,
    collection: 'raw_events',
  }
);

// Unique source + external ID (primary dedupe)
RawEventSchema.index({ sourceType: 1, externalId: 1 }, { unique: true });
// Dedupe lookup
RawEventSchema.index({ dedupeKey: 1, publishedAt: -1 });
// Recent ingest lookup
RawEventSchema.index({ ingestedAt: -1 });
// Intake worker: unprocessed events
RawEventSchema.index({ processed: 1, ingestedAt: 1 });

export const RawEventModel = mongoose.model<IRawEvent>('RawEvent', RawEventSchema);
