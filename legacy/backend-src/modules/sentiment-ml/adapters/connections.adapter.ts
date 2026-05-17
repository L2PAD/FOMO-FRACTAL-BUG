/**
 * Connections Adapter
 * ===================
 * 
 * БЛОК 1: Реальная реализация ConnectionsPort
 * 
 * ПРИНЦИП:
 * - Читает данные из connections_db (MongoDB)
 * - Не импортирует модули Connections напрямую
 * - Graceful fallback при ошибках
 * 
 * ДАННЫЕ:
 * - connections_unified_accounts — профили авторов
 * - connections_clusters — кластеры
 * - narrative_mentions — нарративы (intelligence_engine DB)
 */

import { Db, MongoClient } from 'mongodb';
import { 
  ConnectionsPort, 
  AuthorProfile, 
  ClusterProfile, 
  NarrativeInfo 
} from '../ports/connections.port.js';

export class ConnectionsAdapter implements ConnectionsPort {
  private connectionsDb: Db | null = null;
  private intelligenceDb: Db | null = null;
  private available = false;
  private initialized = false;

  constructor(private mongoClient: MongoClient) {
    this.initDatabases();
  }

  private async initDatabases(): Promise<void> {
    try {
      this.connectionsDb = this.mongoClient.db('connections_db');
      this.intelligenceDb = this.mongoClient.db('intelligence_engine');
      
      // Проверяем доступность коллекции
      const count = await this.connectionsDb
        .collection('connections_unified_accounts')
        .countDocuments();
      
      this.available = count > 0;
      this.initialized = true;
      
      console.log(`[Sentiment] ConnectionsAdapter initialized - ${count} accounts available`);
    } catch (error) {
      console.error('[Sentiment] Failed to init ConnectionsAdapter:', error);
      this.available = false;
      this.initialized = true;
    }
  }

  async getAuthorProfile(authorId: string): Promise<AuthorProfile | null> {
    if (!this.available || !this.connectionsDb) {
      return null;
    }

    try {
      // Ищем по handle (lowercase)
      const handle = authorId.toLowerCase().replace('@', '');
      
      const account = await this.connectionsDb
        .collection('connections_unified_accounts')
        .findOne(
          { $or: [
            { handle: handle },
            { handle: `@${handle}` },
            { author_id: authorId }
          ]},
          { projection: { _id: 0 } }
        );

      if (!account) {
        return null;
      }

      return {
        authorScore: account.influence ?? account.confidence ?? 0.5,
        botProb: account.botProb ?? (1 - (account.confidence || 0.5)),
        influence: account.influence ?? 0.5,
        hitRate1d: account.hitRate1d,
        hitRate7d: account.hitRate7d,
        hitRate30d: account.hitRate30d,
        clusterId: account.clusterId,
        categories: account.categories || [],
      };
    } catch (error) {
      console.error('[Sentiment] getAuthorProfile error:', error);
      return null;
    }
  }

  async getClusterProfile(clusterId: string): Promise<ClusterProfile | null> {
    if (!this.available || !this.connectionsDb) {
      return null;
    }

    try {
      // Сначала пробуем найти в connections_clusters
      const cluster = await this.connectionsDb
        .collection('connections_clusters')
        .findOne(
          { $or: [{ name: clusterId }] },
          { projection: { _id: 0 } }
        );

      if (cluster) {
        return {
          clusterScore: (cluster.avgInfluence || 500) / 1000,
          manipulationProb: cluster.manipulationProb ?? 0.2,
          memberCount: cluster.memberCount,
          avgInfluence: cluster.avgInfluence,
        };
      }

      // Если начинается с cat_ — это category-based cluster
      if (clusterId.startsWith('cat_')) {
        const category = clusterId.replace('cat_', '');
        
        const stats = await this.connectionsDb
          .collection('connections_unified_accounts')
          .aggregate([
            { $match: { categories: category } },
            { $group: {
              _id: null,
              count: { $sum: 1 },
              avgInfluence: { $avg: '$influence' },
              avgConfidence: { $avg: '$confidence' },
            }}
          ])
          .toArray();

        if (stats.length > 0) {
          return {
            clusterScore: stats[0].avgConfidence || 0.5,
            manipulationProb: 0.1, // Category clusters менее подозрительны
            memberCount: stats[0].count,
            avgInfluence: stats[0].avgInfluence,
          };
        }
      }

      return null;
    } catch (error) {
      console.error('[Sentiment] getClusterProfile error:', error);
      return null;
    }
  }

  async getNarrative(symbol: string, ts: number): Promise<NarrativeInfo | null> {
    if (!this.intelligenceDb) {
      return null;
    }

    try {
      const symbolUpper = symbol.toUpperCase();
      
      // Ищем нарративы связанные с символом за последние 24ч
      const windowMs = 24 * 60 * 60 * 1000;
      const since = new Date(ts - windowMs);
      
      const mentions = await this.intelligenceDb
        .collection('narrative_mentions')
        .find({
          tokens: symbolUpper,
          createdAt: { $gte: since },
        })
        .sort({ createdAt: -1 })
        .limit(10)
        .toArray();

      if (mentions.length === 0) {
        return null;
      }

      // Группируем по нарративу и выбираем самый активный
      const narrativeMap = new Map<string, { count: number; confidence: number; phase: string }>();
      
      for (const m of mentions) {
        const key = m.narrative || m.topic || 'general';
        const existing = narrativeMap.get(key) || { count: 0, confidence: 0, phase: m.phase || 'MID' };
        existing.count++;
        existing.confidence = Math.max(existing.confidence, m.confidence || 0);
        narrativeMap.set(key, existing);
      }

      // Находим топовый нарратив
      let topNarrative = { id: 'general', count: 0, confidence: 0, phase: 'MID' };
      narrativeMap.forEach((data, id) => {
        if (data.count > topNarrative.count) {
          topNarrative = { id, ...data };
        }
      });

      // Определяем heat (0..1) на основе количества упоминаний
      const heat = Math.min(1, topNarrative.count / 10);

      // Определяем фазу
      let phase: 'EARLY' | 'MID' | 'LATE' | 'DEAD' = 'MID';
      if (topNarrative.phase === 'SEEDING' || topNarrative.phase === 'IGNITING') {
        phase = 'EARLY';
      } else if (topNarrative.phase === 'EXPANDING') {
        phase = 'MID';
      } else if (topNarrative.phase === 'SATURATING' || topNarrative.phase === 'FADING') {
        phase = 'LATE';
      } else if (topNarrative.phase === 'DEAD') {
        phase = 'DEAD';
      }

      return {
        narrativeId: topNarrative.id,
        heat,
        phase,
        mentionCount: topNarrative.count,
        topTokens: [symbolUpper],
      };
    } catch (error) {
      console.error('[Sentiment] getNarrative error:', error);
      return null;
    }
  }

  isAvailable(): boolean {
    return this.available;
  }
}
