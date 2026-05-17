/**
 * Sentiment-ML Admin Routes
 * =========================
 * 
 * API для управления и мониторинга Sentiment-ML модуля
 * 
 * Endpoints:
 * - GET /api/admin/sentiment-ml/status — статус модуля
 * - GET /api/admin/sentiment-ml/enrichment/stats — статистика enrichment
 * - POST /api/admin/sentiment-ml/enrichment/test — тест enrichment на твите
 */

import type { FastifyInstance } from 'fastify';
import { 
  getSentimentMLStatus, 
  getSentimentEnrichmentService,
  isSentimentMLInitialized,
} from '../index.js';

export async function registerSentimentMLAdminRoutes(app: FastifyInstance): Promise<void> {

  /**
   * GET /status — Полный статус Sentiment-ML модуля
   */
  app.get('/status', async () => {
    try {
      const status = getSentimentMLStatus();
      
      return {
        ok: true,
        data: {
          ...status,
          version: '1.0.0-block1',
          phase: 'BLOCK_1_CONNECTIONS_ADAPTER',
          description: 'Connections integration via port/adapter pattern',
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * GET /enrichment/stats — Статистика enrichment
   */
  app.get('/enrichment/stats', async () => {
    try {
      if (!isSentimentMLInitialized()) {
        return {
          ok: false,
          error: 'Sentiment-ML module not initialized',
        };
      }

      const service = getSentimentEnrichmentService();
      const stats = service.getStats();
      const connectionsAvailable = service.isConnectionsAvailable();

      return {
        ok: true,
        data: {
          connectionsAvailable,
          stats,
          rates: {
            authorEnrichRate: stats.totalEnriched > 0 
              ? (stats.withAuthor / stats.totalEnriched * 100).toFixed(1) + '%'
              : '0%',
            clusterEnrichRate: stats.totalEnriched > 0
              ? (stats.withCluster / stats.totalEnriched * 100).toFixed(1) + '%'
              : '0%',
            narrativeEnrichRate: stats.totalEnriched > 0
              ? (stats.withNarrative / stats.totalEnriched * 100).toFixed(1) + '%'
              : '0%',
            failureRate: stats.totalEnriched > 0
              ? (stats.failedEnrichments / stats.totalEnriched * 100).toFixed(1) + '%'
              : '0%',
          },
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * POST /enrichment/test — Тестовый enrichment твита
   * 
   * Body:
   * {
   *   authorId: string,
   *   text: string,
   *   symbol?: string
   * }
   */
  app.post('/enrichment/test', async (request) => {
    try {
      if (!isSentimentMLInitialized()) {
        return {
          ok: false,
          error: 'Sentiment-ML module not initialized',
        };
      }

      const body = request.body as {
        authorId?: string;
        text?: string;
        symbol?: string;
      };

      if (!body.authorId) {
        return {
          ok: false,
          error: 'authorId is required',
        };
      }

      const service = getSentimentEnrichmentService();
      
      const enrichment = await service.enrichTweet({
        authorId: body.authorId,
        text: body.text || '',
        symbol: body.symbol,
        timestamp: Date.now(),
      });

      return {
        ok: true,
        data: {
          input: {
            authorId: body.authorId,
            symbol: body.symbol,
          },
          enrichment: {
            connectionsAvailable: enrichment.connectionsAvailable,
            hasAuthorProfile: !!enrichment.authorProfile,
            hasClusterProfile: !!enrichment.clusterProfile,
            hasNarrative: !!enrichment.narrative,
            authorProfile: enrichment.authorProfile,
            clusterProfile: enrichment.clusterProfile,
            narrative: enrichment.narrative,
            enrichedAt: new Date(enrichment.enrichedAt).toISOString(),
          },
        },
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  /**
   * POST /enrichment/reset — Сбросить статистику enrichment
   */
  app.post('/enrichment/reset', async () => {
    try {
      if (!isSentimentMLInitialized()) {
        return {
          ok: false,
          error: 'Sentiment-ML module not initialized',
        };
      }

      const service = getSentimentEnrichmentService();
      service.resetStats();

      return {
        ok: true,
        message: 'Enrichment stats reset',
      };
    } catch (error: any) {
      return {
        ok: false,
        error: error.message,
      };
    }
  });

  console.log('[Sentiment-ML] Admin routes registered at /api/admin/sentiment-ml/*');
}
