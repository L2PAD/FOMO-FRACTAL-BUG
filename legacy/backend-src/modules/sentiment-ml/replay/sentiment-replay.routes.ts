/**
 * Sentiment Historical Replay Routes
 * ====================================
 * 
 * Admin API for historical replay management.
 * 
 * Endpoints:
 * - GET /status — Current replay progress
 * - POST /start — Start historical replay
 * - POST /abort — Abort running replay
 * - GET /estimate — Estimate replay duration
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { 
  getSentimentReplayService, 
  ReplayConfig,
  REPLAY_SYMBOLS 
} from './sentiment-historical-replay.service.js';

interface StartReplayBody {
  daysBack?: number;
  tweetsPerDayPerSymbol?: number;
  delayMs?: number;
  concurrency?: number;
}

async function sentimentReplayRoutes(app: FastifyInstance): Promise<void> {
  const service = getSentimentReplayService();
  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  /**
   * GET /status — Get current replay progress
   */
  app.get('/status', async () => {
    const progress = service.getProgress();
    
    return {
      ok: true,
      progress,
      symbols: REPLAY_SYMBOLS,
    };
  });

  /**
   * POST /start — Start historical replay
   */
  app.post('/start', async (req: FastifyRequest<{ Body: StartReplayBody }>) => {
    const body = req.body || {};
    
    const progress = service.getProgress();
    if (progress.status === 'RUNNING') {
      return {
        ok: false,
        error: 'Replay already running',
        progress,
      };
    }

    const config: ReplayConfig = {
      daysBack: body.daysBack || 60,
      tweetsPerDayPerSymbol: body.tweetsPerDayPerSymbol || 30,
      delayBetweenRequests: body.delayMs || 1500,
      parserUrl: backendUrl,
      userId: 'system-replay',
      concurrency: body.concurrency || 4,
      maxRetries: 3,
    };

    // Run in background
    service.runReplay(config).catch(err => {
      console.error('[Replay] Background error:', err);
    });

    // Return immediately with estimate
    const estimate = service.estimateDuration(config);

    return {
      ok: true,
      message: 'Replay started in background',
      config,
      estimate,
    };
  });

  /**
   * POST /abort — Abort running replay
   */
  app.post('/abort', async () => {
    const progress = service.getProgress();
    
    if (progress.status !== 'RUNNING') {
      return {
        ok: false,
        error: 'No replay running',
        progress,
      };
    }

    service.abort();

    return {
      ok: true,
      message: 'Abort requested',
    };
  });

  /**
   * GET /estimate — Estimate replay duration
   */
  app.get('/estimate', async (req: FastifyRequest<{ Querystring: { days?: string } }>) => {
    const daysBack = parseInt(req.query.days || '60', 10);

    const config: ReplayConfig = {
      daysBack,
      tweetsPerDayPerSymbol: 30,
      delayBetweenRequests: 1500,
      parserUrl: '',
      userId: '',
    };

    const estimate = service.estimateDuration(config);

    return {
      ok: true,
      daysBack,
      symbols: REPLAY_SYMBOLS.length,
      ...estimate,
    };
  });

  /**
   * POST /process-existing — Process existing parsed tweets through sentiment pipeline
   */
  app.post('/process-existing', async () => {
    const mongoose = (await import('mongoose')).default;
    const db = mongoose.connection.db;
    
    if (!db) {
      return {
        ok: false,
        error: 'Database not connected',
      };
    }

    const { getExistingTweetsProcessor } = await import('./sentiment-existing-tweets.processor.js');
    const processor = getExistingTweetsProcessor();
    
    const result = await processor.processExistingTweets(db);

    return {
      ok: true,
      result,
    };
  });

  /**
   * POST /parse-admin — Admin parse endpoint using system session directly
   * Bypasses user auth for historical replay
   */
  app.post('/parse-admin', async (req: FastifyRequest<{ Body: { query: string; limit?: number; dateRange?: { since: string; until: string } } }>) => {
    const body = req.body || {};
    const { query, limit = 30, dateRange } = body;

    if (!query) {
      return { ok: false, error: 'Missing query' };
    }

    try {
      const mongoose = (await import('mongoose')).default;
      const db = mongoose.connection.db;
      if (!db) {
        return { ok: false, error: 'Database not connected' };
      }

      // Get session with most cookies (prefer latest synced)
      const sessionsCol = db.collection('twitter_sessions');
      const sessions = await sessionsCol.find({
        encryptedCookies: { $exists: true, $ne: '' },
        'cookiesMeta.hasAuthToken': true,
        'cookiesMeta.hasCt0': true,
      }).sort({ 'cookiesMeta.count': -1, lastSyncedAt: -1 }).limit(1).toArray();

      const session = sessions[0];
      if (!session) {
        return { ok: false, error: 'NO_SESSION', message: 'No session with valid cookies found' };
      }

      // Debug: log what we got from DB
      const encStr = session.encryptedCookies || '';
      const cookieCount = session.cookiesMeta?.count || 0;
      console.log(`[ParseAdmin] DB session found: ${session.sessionId}`);
      console.log(`[ParseAdmin] Cookie meta count: ${cookieCount}`);
      console.log(`[ParseAdmin] encryptedCookies length: ${encStr.length}`);
      console.log(`[ParseAdmin] encryptedCookies preview: ${encStr.slice(0, 100)}...`);

      // Decrypt cookies using the correct module
      const { decryptCookies } = await import('../../twitter/sessions/session.crypto.js');
      
      let cookies: Array<{ name: string; value: string; domain: string }> = [];
      try {
        cookies = decryptCookies(session.encryptedCookies);
      } catch (e) {
        return { ok: false, error: 'DECRYPT_FAILED', message: 'Could not decrypt cookies' };
      }

      if (!cookies || cookies.length === 0) {
        return { ok: false, error: 'NO_COOKIES', message: 'Session has no cookies after decryption' };
      }

      // Log cookie details
      const authToken = cookies.find((c: any) => c.name === 'auth_token');
      const ct0 = cookies.find((c: any) => c.name === 'ct0');
      console.log(`[ParseAdmin] Got ${cookies.length} cookies:`);
      console.log(`[ParseAdmin]   auth_token: ${authToken ? 'present' : 'MISSING'}`);
      console.log(`[ParseAdmin]   ct0: ${ct0 ? 'present' : 'MISSING'}`);
      console.log(`[ParseAdmin] Calling parser for "${query}"...`);

      // Call parser directly - using /search/:query endpoint
      const parserUrl = process.env.TWITTER_PARSER_URL || 'http://localhost:5001';
      const axios = (await import('axios')).default;

      const parseResponse = await axios.post(
        `${parserUrl}/search/${encodeURIComponent(query)}`,
        {
          limit,
          cookies,
          dateRange,
          userAgent: session.userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        },
        {
          timeout: 120000,
          headers: { 'Content-Type': 'application/json' },
        }
      );

      const tweets = parseResponse.data?.data?.tweets || parseResponse.data?.tweets || [];
      
      console.log(`[ParseAdmin] Parser response keys: ${Object.keys(parseResponse.data || {})}`);
      console.log(`[ParseAdmin] Parser data keys: ${Object.keys(parseResponse.data?.data || {})}`);
      console.log(`[ParseAdmin] Tweets array length: ${tweets.length}`);
      if (tweets.length > 0) {
        console.log(`[ParseAdmin] First tweet keys: ${Object.keys(tweets[0]).slice(0, 10).join(', ')}`);
      }

      // Save tweets to sentiment pipeline
      if (tweets.length > 0) {
        const { SentimentEventModel } = await import('../storage/sentiment-event.model.js');
        const { extractSymbols } = await import('../runtime/symbol-extractor.js');
        const { sentimentWeightingService } = await import('../engines/sentiment-weighting.service.js');

        let created = 0;

        for (const tweet of tweets) {
          const text = tweet.text || tweet.content || '';
          const symbols = extractSymbols(text);
          
          if (symbols.length === 0) {
            console.log(`[ParseAdmin] Tweet (no symbols): "${text.slice(0, 60)}..."`);
            continue;
          }
          
          console.log(`[ParseAdmin] Tweet: "${text.slice(0, 100)}..." → Symbols: [${symbols.join(', ')}]`);
          
          for (const symbol of symbols) {
            try {
              const tweetCreatedAt = tweet.createdAt ? new Date(tweet.createdAt) : new Date();
              
              const weighted = sentimentWeightingService.compute({
                baseScore: 0.5 + Math.random() * 0.2 - 0.1, // Placeholder
                baseConfidence: 'MEDIUM',
                tweetCreatedAt,
                authorScore: 0.5,
                influence: 0.5,
                botProb: 0.1,
              });

              await SentimentEventModel.create({
                tweetId: tweet.id || tweet.tweetId || `gen_${Date.now()}_${Math.random().toString(36).slice(2)}`,
                symbol,
                tweetCreatedAt,
                authorHandle: tweet.author?.username || tweet.user?.username || 'unknown',
                baseLabel: 'NEUTRAL',
                baseScore: 0.5,
                baseConfidence: 'MEDIUM',
                weightedScore: weighted.weightedScore,
                weightedConfidence: weighted.weightedConfidence,
                processedAt: new Date(),
                processingVersion: 'replay-admin-v1',
              });
              created++;
              console.log(`[ParseAdmin] Created event for ${symbol} from tweet ${tweet.id}`);
            } catch (e: any) {
              if (e.code === 11000) {
                console.log(`[ParseAdmin] Skipped duplicate: ${tweet.id} / ${symbol}`);
              } else {
                console.error('[ParseAdmin] Error creating event:', e.message);
              }
            }
          }
        }

        return {
          ok: true,
          fetched: tweets.length,
          eventsCreated: created,
          session: { id: session.sessionId, username: session.accountId?.username },
        };
      }

      return {
        ok: true,
        fetched: 0,
        message: 'No tweets returned from parser',
        parserResponse: parseResponse.data,
      };

    } catch (err: any) {
      console.error('[ParseAdmin] Error:', err.message);
      return {
        ok: false,
        error: err.message,
        code: err.code || 'UNKNOWN',
      };
    }
  });

  /**
   * POST /full-backfill — Start full historical backfill in background (60 days)
   * Returns immediately, job runs in background
   */
  app.post('/full-backfill', async (req: FastifyRequest<{ Body: { daysBack?: number; symbolsPerBatch?: number; delayMs?: number } }>) => {
    const body = req.body || {};
    const daysBack = body.daysBack || 60;
    const symbolsPerBatch = body.symbolsPerBatch || 4;
    const delayBetweenDays = body.delayMs || 3000;

    // Start backfill in background
    runBackfillJob({
      daysBack,
      symbolsPerBatch,
      delayBetweenDays,
    }).catch(err => {
      console.error('[FullBackfill] Background job failed:', err.message);
    });

    return {
      ok: true,
      message: 'Backfill job started in background',
      config: { daysBack, symbolsPerBatch, delayBetweenDays },
      checkProgress: 'GET /api/admin/sentiment-ml/replay/backfill-status',
    };
  });

  /**
   * GET /backfill-status — Check backfill job progress
   */
  app.get('/backfill-status', async () => {
    return {
      ok: true,
      progress: backfillProgress,
    };
  });

  console.log('[Sentiment-ML] Replay admin routes registered');
}

// Backfill progress tracker
let backfillProgress: {
  status: 'IDLE' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  daysTotal: number;
  daysProcessed: number;
  currentDay: string;
  totalEvents: number;
  totalSamplesCreated: number;
  errors: string[];
  startedAt?: Date;
  completedAt?: Date;
} = {
  status: 'IDLE',
  daysTotal: 0,
  daysProcessed: 0,
  currentDay: '',
  totalEvents: 0,
  totalSamplesCreated: 0,
  errors: [],
};

async function runBackfillJob(config: {
  daysBack: number;
  symbolsPerBatch: number;
  delayBetweenDays: number;
}) {
  const { daysBack, symbolsPerBatch, delayBetweenDays } = config;

  const SYMBOLS = [
    'BTC', 'ETH', 'SOL', 'XRP', 'BNB',
    'ADA', 'AVAX', 'DOGE', 'LINK', 'MATIC',
    'DOT', 'LTC', 'TRX', 'UNI', 'ATOM',
    'APT', 'ARB', 'OP', 'INJ', 'SUI'
  ];

  // Reset progress
  backfillProgress = {
    status: 'RUNNING',
    daysTotal: daysBack,
    daysProcessed: 0,
    currentDay: '',
    totalEvents: 0,
    totalSamplesCreated: 0,
    errors: [],
    startedAt: new Date(),
  };

  try {
    const mongoose = (await import('mongoose')).default;
    const db = mongoose.connection.db;
    if (!db) {
      backfillProgress.status = 'FAILED';
      backfillProgress.errors.push('Database not connected');
      return;
    }

    // Get session
    const sessionsCol = db.collection('twitter_sessions');
    const sessions = await sessionsCol.find({
      encryptedCookies: { $exists: true, $ne: '' },
      'cookiesMeta.hasAuthToken': true,
      'cookiesMeta.hasCt0': true,
    }).sort({ 'cookiesMeta.count': -1 }).limit(1).toArray();

    if (!sessions[0]) {
      backfillProgress.status = 'FAILED';
      backfillProgress.errors.push('No valid session found');
      return;
    }

    // Import dependencies
    const { decryptCookies } = await import('../../twitter/sessions/session.crypto.js');
    const { SentimentEventModel } = await import('../storage/sentiment-event.model.js');
    const { SentimentAggregateModel } = await import('../storage/sentiment-aggregate.model.js');
    const { extractSymbols } = await import('../runtime/symbol-extractor.js');
    const { sentimentWeightingService } = await import('../engines/sentiment-weighting.service.js');
    const { sentimentAggregationService } = await import('../services/sentiment-aggregation.service.js');
    const { SentimentDatasetAccumulator } = await import('../dataset/sentiment-dataset.accumulator.js');
    const { getSentimentPriceAdapter } = await import('../dataset/sentiment-price.adapter.js');
    const axios = (await import('axios')).default;

    const cookies = decryptCookies(sessions[0].encryptedCookies);
    if (!cookies || cookies.length < 10) {
      backfillProgress.status = 'FAILED';
      backfillProgress.errors.push('Invalid cookies');
      return;
    }

    const parserUrl = process.env.TWITTER_PARSER_URL || 'http://localhost:5001';
    const accumulator = new SentimentDatasetAccumulator(getSentimentPriceAdapter());

    console.log(`[FullBackfill] Starting ${daysBack}-day backfill with ${SYMBOLS.length} symbols`);

    const today = new Date();

    // Process each day from oldest to newest
    for (let dayOffset = daysBack; dayOffset >= 1; dayOffset--) {
      const targetDate = new Date(today);
      targetDate.setDate(today.getDate() - dayOffset);
      targetDate.setHours(0, 0, 0, 0);

      const nextDate = new Date(targetDate);
      nextDate.setDate(targetDate.getDate() + 1);

      const since = targetDate.toISOString().split('T')[0];
      const until = nextDate.toISOString().split('T')[0];

      backfillProgress.currentDay = since;
      console.log(`[FullBackfill] Day ${daysBack - dayOffset + 1}/${daysBack}: ${since}`);

      let dayEvents = 0;

      // Process symbols in batches
      for (let i = 0; i < SYMBOLS.length; i += symbolsPerBatch) {
        const batch = SYMBOLS.slice(i, i + symbolsPerBatch);

        // Parse each symbol in batch (parallel)
        await Promise.all(batch.map(async (symbol) => {
          try {
            // Twitter search with date range uses syntax: query since:YYYY-MM-DD until:YYYY-MM-DD
            const searchQuery = `$${symbol} since:${since} until:${until}`;
            
            const response = await axios.post(
              `${parserUrl}/search/${encodeURIComponent(searchQuery)}`,
              {
                limit: 15,
                cookies,
              },
              { timeout: 120000 }
            );

            const tweets = response.data?.data?.tweets || [];
            
            for (const tweet of tweets) {
              const text = tweet.text || '';
              const symbols = extractSymbols(text);

              for (const sym of symbols) {
                try {
                  const tweetCreatedAt = tweet.createdAt ? new Date(tweet.createdAt) : targetDate;
                  const weighted = sentimentWeightingService.compute({
                    baseScore: 0.5,
                    baseConfidence: 'MEDIUM',
                    tweetCreatedAt,
                  });

                  await SentimentEventModel.create({
                    tweetId: tweet.id || `backfill_${Date.now()}_${Math.random().toString(36).slice(2)}`,
                    symbol: sym,
                    tweetCreatedAt,
                    authorHandle: tweet.author?.username || 'unknown',
                    baseLabel: 'NEUTRAL',
                    baseScore: 0.5,
                    baseConfidence: 'MEDIUM',
                    weightedScore: weighted.weightedScore,
                    weightedConfidence: weighted.weightedConfidence,
                    processedAt: new Date(),
                    processingVersion: 'backfill-v1',
                  });
                  dayEvents++;
                  backfillProgress.totalEvents++;
                } catch (e: any) {
                  if (e.code !== 11000) {
                    backfillProgress.errors.push(`Event: ${e.message.slice(0, 100)}`);
                  }
                }
              }
            }
          } catch (e: any) {
            if (!e.message.includes('aborted')) {
              backfillProgress.errors.push(`Parse ${symbol}: ${e.message.slice(0, 100)}`);
            }
          }
        }));

        // Small delay between batches
        await new Promise(r => setTimeout(r, 1000));
      }

      // Create aggregates for this day
      for (const symbol of SYMBOLS) {
        try {
          const asOf = new Date(targetDate);
          asOf.setHours(12, 0, 0, 0);
          await sentimentAggregationService.aggregateSymbol(symbol, '24H', asOf);
        } catch {
          // Silent
        }
      }

      // Finalize samples in backfill mode
      const aggregates = await SentimentAggregateModel.find({
        asOf: { $gte: targetDate, $lt: nextDate },
        window: '24H',
      }).lean();

      for (const agg of aggregates) {
        try {
          const result = await accumulator.finalizeSample({
            symbol: agg.symbol,
            window: '24H',
            asOf: agg.asOf,
            mode: 'backfill',
          });

          if (result.status === 'CREATED') {
            backfillProgress.totalSamplesCreated++;
          }
        } catch (e: any) {
          backfillProgress.errors.push(`Finalize: ${e.message.slice(0, 100)}`);
        }
      }

      backfillProgress.daysProcessed++;
      console.log(`[FullBackfill] Day ${since}: ${dayEvents} events, ${aggregates.length} aggregates`);

      // Rate limit between days
      await new Promise(r => setTimeout(r, delayBetweenDays));

      // Keep errors limited
      if (backfillProgress.errors.length > 50) {
        backfillProgress.errors = backfillProgress.errors.slice(-50);
      }
    }

    backfillProgress.status = 'COMPLETED';
    backfillProgress.completedAt = new Date();
    console.log(`[FullBackfill] DONE: ${backfillProgress.totalEvents} events, ${backfillProgress.totalSamplesCreated} samples`);

  } catch (err: any) {
    backfillProgress.status = 'FAILED';
    backfillProgress.errors.push(`Fatal: ${err.message}`);
    console.error('[FullBackfill] Fatal error:', err.message);
  }
}

// Export wrapped in fastify-plugin
export default fp(sentimentReplayRoutes, {
  name: 'sentiment-replay-routes',
  fastify: '4.x',
});

export { sentimentReplayRoutes };
