/**
 * Bridge Twitter Adapter
 * ======================
 * Reads from user_twitter_parsed_tweets and normalizes to UnifiedTextEvent.
 * This is the primary ingestion source until twitter-parser-v2 is online.
 */

import mongoose from 'mongoose';
import type { IngestionAdapter, UnifiedTextEvent, SourceType } from '../ingestion.types.js';

class BridgeTwitterAdapter implements IngestionAdapter {
  sourceType: SourceType = 'twitter';
  sourceName = 'twitter-bridge';

  async fetch(params?: {
    limit?: number;
    sinceMinutes?: number;
    seedAll?: boolean;
  }): Promise<UnifiedTextEvent[]> {
    const db = mongoose.connection.db;
    if (!db) {
      console.warn('[BridgeTwitterAdapter] MongoDB not connected');
      return [];
    }

    const limit = params?.limit ?? 200;
    const collection = db.collection('user_twitter_parsed_tweets');

    let filter: Record<string, any> = {};
    if (!params?.seedAll && params?.sinceMinutes) {
      const since = new Date(Date.now() - params.sinceMinutes * 60 * 1000);
      filter = { createdAt: { $gte: since } };
    }

    const docs = await collection
      .find(filter)
      .sort({ createdAt: -1 })
      .limit(limit)
      .toArray();

    return docs.map((doc) => this.normalize(doc));
  }

  private normalize(doc: any): UnifiedTextEvent {
    return {
      externalId: String(doc.tweetId || doc._id),
      sourceType: 'twitter',
      sourceName: this.sourceName,

      text: String(doc.text || '').trim(),
      url: doc.url,

      publishedAt: new Date(doc.tweetedAt || doc.createdAt || Date.now()),
      ingestedAt: new Date(),

      author: {
        id: doc.author?.id,
        handle: doc.author?.username || doc.username,
        name: doc.author?.name || doc.displayName,
        followers: doc.author?.followers,
        verified: doc.author?.verified,
      },

      engagement: {
        likes: doc.likes || 0,
        reposts: doc.reposts || 0,
        replies: doc.replies || 0,
        views: doc.views || 0,
      },

      assetMentions: [],
      projectMentions: [],

      dedupeKey: '',
      raw: {
        tweetId: doc.tweetId,
        source: doc.source,
        targetUsername: doc.targetUsername,
        query: doc.query,
        media: doc.media,
        accountId: doc.accountId,
        sessionId: doc.sessionId,
        taskId: doc.taskId,
      },
    };
  }
}

export const bridgeTwitterAdapter = new BridgeTwitterAdapter();
