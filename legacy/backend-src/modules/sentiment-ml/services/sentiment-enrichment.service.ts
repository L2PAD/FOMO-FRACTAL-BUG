/**
 * Sentiment Enrichment Service
 * ============================
 * 
 * БЛОК 1: Enrichment pipeline — обогащение твитов данными Connections
 * 
 * ПРИНЦИП:
 * - Каждый твит проходит через enrichment
 * - Получаем: authorProfile, clusterProfile, narrative
 * - Graceful fallback если Connections недоступен
 * 
 * ПОКА НЕ ДЕЛАЕМ (Блок 2):
 * - Взвешенный scoring
 * - Формула weight
 * 
 * СЕЙЧАС:
 * - Просто сохраняем enrichment в объект анализа
 */

import { 
  ConnectionsPort, 
  AuthorProfile, 
  ClusterProfile, 
  NarrativeInfo 
} from '../ports/connections.port.js';

export interface TweetEnrichment {
  authorProfile: AuthorProfile | null;
  clusterProfile: ClusterProfile | null;
  narrative: NarrativeInfo | null;
  enrichedAt: number;
  connectionsAvailable: boolean;
}

export interface EnrichmentStats {
  totalEnriched: number;
  withAuthor: number;
  withCluster: number;
  withNarrative: number;
  failedEnrichments: number;
}

export class SentimentEnrichmentService {
  private stats: EnrichmentStats = {
    totalEnriched: 0,
    withAuthor: 0,
    withCluster: 0,
    withNarrative: 0,
    failedEnrichments: 0,
  };

  constructor(private connections: ConnectionsPort) {
    console.log('[SentimentEnrichment] Service initialized');
  }

  /**
   * Обогатить твит данными из Connections
   */
  async enrichTweet(tweet: {
    authorId: string;
    text: string;
    symbol?: string;
    timestamp?: number;
  }): Promise<TweetEnrichment> {
    const ts = tweet.timestamp || Date.now();
    
    // Если Connections недоступен — возвращаем пустой enrichment
    if (!this.connections.isAvailable()) {
      return {
        authorProfile: null,
        clusterProfile: null,
        narrative: null,
        enrichedAt: ts,
        connectionsAvailable: false,
      };
    }

    try {
      // 1. Получаем профиль автора
      const authorProfile = await this.connections.getAuthorProfile(tweet.authorId);
      
      // 2. Если есть clusterId — получаем профиль кластера
      let clusterProfile: ClusterProfile | null = null;
      if (authorProfile?.clusterId) {
        clusterProfile = await this.connections.getClusterProfile(authorProfile.clusterId);
      }
      
      // 3. Если есть символ — получаем нарратив
      let narrative: NarrativeInfo | null = null;
      if (tweet.symbol) {
        narrative = await this.connections.getNarrative(tweet.symbol, ts);
      }

      // Обновляем статистику
      this.stats.totalEnriched++;
      if (authorProfile) this.stats.withAuthor++;
      if (clusterProfile) this.stats.withCluster++;
      if (narrative) this.stats.withNarrative++;

      // Лог для отладки (временно)
      if (authorProfile) {
        console.log(`[SentimentEnrichment] Author enriched:`, {
          author: tweet.authorId,
          score: authorProfile.authorScore,
          botProb: authorProfile.botProb,
          cluster: authorProfile.clusterId,
          narrativePhase: narrative?.phase,
        });
      }

      return {
        authorProfile,
        clusterProfile,
        narrative,
        enrichedAt: ts,
        connectionsAvailable: true,
      };
    } catch (error) {
      console.error('[SentimentEnrichment] Failed to enrich tweet:', error);
      this.stats.failedEnrichments++;
      
      return {
        authorProfile: null,
        clusterProfile: null,
        narrative: null,
        enrichedAt: ts,
        connectionsAvailable: true, // Connections доступен, но ошибка при запросе
      };
    }
  }

  /**
   * Получить статистику enrichment
   */
  getStats(): EnrichmentStats {
    return { ...this.stats };
  }

  /**
   * Сбросить статистику
   */
  resetStats(): void {
    this.stats = {
      totalEnriched: 0,
      withAuthor: 0,
      withCluster: 0,
      withNarrative: 0,
      failedEnrichments: 0,
    };
  }

  /**
   * Проверить доступность Connections
   */
  isConnectionsAvailable(): boolean {
    return this.connections.isAvailable();
  }
}
