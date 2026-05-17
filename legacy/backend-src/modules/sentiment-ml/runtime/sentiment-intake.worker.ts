/**
 * Sentiment Intake Worker
 * =======================
 * 
 * BLOCK 2A: Background worker для обработки событий
 * 
 * Pipeline:
 * 1. Poll raw_events (новые необработанные события)
 * 2. Extract symbols
 * 3. Classify event type
 * 4. Get base sentiment (MOCK engine)
 * 5. Apply source + event weighting
 * 6. Enrich with Connections data
 * 7. Store in sentiment_events
 * 8. Mark raw_event as processed
 * 
 * Supports: twitter, news, telegram (multi-source)
 */

import mongoose from 'mongoose';
import { SentimentEventModel } from '../storage/sentiment-event.model.js';
import { SentimentProcessingModel } from '../storage/sentiment-processing.model.js';
import { extractSymbols } from './symbol-extractor.js';
import { mockSentimentEngine } from '../engines/mock-sentiment.engine.js';
import { sentimentWeightingService } from '../engines/sentiment-weighting.service.js';
import { getSentimentEnrichmentService, isSentimentMLInitialized } from '../index.js';
import { RawEventModel } from '../../ingestion/models/raw-event.model.js';
import { eventClassifierService } from '../../ingestion/normalizers/event-classifier.service.js';

// Processing version for tracking (Block 3: Weighted Engine)
const PROCESSING_VERSION = '3.0.0-block3';

// Stats
export interface IntakeWorkerStats {
  isRunning: boolean;
  startedAt: Date | null;
  tickCount: number;
  tweetsProcessed: number;
  eventsCreated: number;
  errorsCount: number;
  lastTickAt: Date | null;
  lastError: string | null;
}

export class SentimentIntakeWorker {
  private running = false;
  private startedAt: Date | null = null;
  private stats: IntakeWorkerStats = {
    isRunning: false,
    startedAt: null,
    tickCount: 0,
    tweetsProcessed: 0,
    eventsCreated: 0,
    errorsCount: 0,
    lastTickAt: null,
    lastError: null,
  };

  /**
   * Start the worker loop
   */
  async start(): Promise<void> {
    if (this.running) {
      console.log('[SentimentIntake] Worker already running');
      return;
    }

    this.running = true;
    this.startedAt = new Date();
    this.stats.isRunning = true;
    this.stats.startedAt = this.startedAt;

    const pollMs = parseInt(process.env.SENTIMENT_INTAKE_POLL_MS || '2500', 10);
    
    console.log(`[SentimentIntake] Worker started (poll every ${pollMs}ms)`);

    while (this.running) {
      try {
        await this.tick();
        this.stats.lastTickAt = new Date();
      } catch (error: any) {
        this.stats.errorsCount++;
        this.stats.lastError = error.message;
        console.error('[SentimentIntake] tick error:', error.message);
      }
      
      await this.sleep(pollMs);
    }

    console.log('[SentimentIntake] Worker stopped');
  }

  /**
   * Stop the worker
   */
  stop(): void {
    this.running = false;
    this.stats.isRunning = false;
    console.log('[SentimentIntake] Stop requested');
  }

  /**
   * Get current stats
   */
  getStats(): IntakeWorkerStats {
    return { ...this.stats };
  }

  /**
   * Single tick of processing
   * Reads from raw_events (multi-source) and creates sentiment_events.
   */
  private async tick(): Promise<void> {
    this.stats.tickCount++;

    const batch = parseInt(process.env.SENTIMENT_INTAKE_BATCH || '50', 10);
    const maxSymbols = parseInt(process.env.SENTIMENT_INTAKE_MAX_SYMBOLS_PER_TWEET || '3', 10);

    // 1. Find unprocessed raw_events
    const rawEvents = await RawEventModel.find({ processed: { $ne: true } })
      .sort({ ingestedAt: 1 })
      .limit(batch)
      .lean();

    // Fallback: also check legacy twitter_results
    if (!rawEvents.length) {
      await this.tickLegacy();
      return;
    }

    // 2. Process each raw event
    for (const event of rawEvents) {
      const externalId = event.externalId;

      try {
        const text = event.text || '';
        const symbols = extractSymbols(text, maxSymbols);

        // Mark as processed even if no symbols (to not reprocess)
        if (!symbols.length) {
          await RawEventModel.updateOne(
            { _id: event._id },
            { $set: { processed: true, processedAt: new Date() } }
          );
          this.stats.tweetsProcessed++;
          continue;
        }

        // Classify event type (rule-based)
        const eventType = eventClassifierService.classify(text);
        const eventImpactWeight = eventClassifierService.getEventImpactWeight(eventType);
        const sourceWeight = eventClassifierService.getSourceWeight(event.sourceType);

        // Get base sentiment
        const baseSentiment = mockSentimentEngine.analyze(text);

        // Get enrichment (if available)
        let enrichment = {
          connectionsAvailable: false,
          authorProfile: null as any,
          clusterProfile: null as any,
          narrative: null as any,
        };

        if (isSentimentMLInitialized()) {
          try {
            const enrichmentService = getSentimentEnrichmentService();
            enrichment = await enrichmentService.enrichTweet({
              authorId: event.author?.handle || '',
              text,
              symbol: symbols[0],
              timestamp: event.publishedAt?.getTime() || Date.now(),
            });
          } catch (enrichErr) {
            // Non-fatal
          }
        }

        // Create sentiment events (one per symbol)
        for (const symbol of symbols) {
          const tweetCreatedAt = event.publishedAt || new Date();

          // Block 3: Calculate weighted score (with source + event impact)
          const weighting = sentimentWeightingService.compute({
            baseScore: baseSentiment.score,
            baseConfidence: baseSentiment.confidence,
            tweetCreatedAt,
            authorScore: enrichment.authorProfile?.authorScore,
            influence: enrichment.authorProfile?.influence,
            botProb: enrichment.authorProfile?.botProb,
          });

          // Apply source and event impact multipliers
          const adjustedScore = weighting.weightedScore * sourceWeight * eventImpactWeight;

          const result = await SentimentEventModel.updateOne(
            { tweetId: externalId, symbol },
            {
              $setOnInsert: {
                tweetId: externalId,
                symbol,
                tweetCreatedAt,
                authorHandle: event.author?.handle || undefined,
                authorId: event.author?.id || undefined,
              },
              $set: {
                // Base sentiment
                baseLabel: baseSentiment.label,
                baseScore: baseSentiment.score,
                baseConfidence: baseSentiment.confidence,

                // Event classification
                eventType,
                eventImpactWeight,
                sourceType: event.sourceType,
                sourceWeight,

                // Connections enrichment
                connectionsAvailable: enrichment.connectionsAvailable,
                authorScore: enrichment.authorProfile?.authorScore,
                influence: enrichment.authorProfile?.influence,
                botProb: enrichment.authorProfile?.botProb,
                clusterId: enrichment.authorProfile?.clusterId,
                clusterScore: enrichment.clusterProfile?.clusterScore,
                manipulationProb: enrichment.clusterProfile?.manipulationProb,
                narrativeId: enrichment.narrative?.narrativeId,
                narrativePhase: enrichment.narrative?.phase,
                narrativeHeat: enrichment.narrative?.heat,

                // Block 3: Weighted scores (with source + event adjustments)
                weightedScore: adjustedScore,
                weightedConfidence: weighting.weightedConfidence,

                // Processing metadata
                processedAt: new Date(),
                processingVersion: PROCESSING_VERSION,
              },
            },
            { upsert: true }
          );

          if (result.upsertedCount > 0) {
            this.stats.eventsCreated++;
          }
        }

        // Mark raw_event as processed
        await RawEventModel.updateOne(
          { _id: event._id },
          { $set: { processed: true, processedAt: new Date() } }
        );

        this.stats.tweetsProcessed++;

      } catch (tweetError: any) {
        await RawEventModel.updateOne(
          { _id: event._id },
          { $set: { lastError: tweetError.message }, $inc: { errorCount: 1 } }
        ).catch(() => {});

        this.stats.errorsCount++;
        console.error(`[SentimentIntake] Event ${externalId} error:`, tweetError.message);
      }
    }
  }

  /**
   * Legacy tick: process from twitter_results for backward compat
   */
  private async tickLegacy(): Promise<void> {
    const db = mongoose.connection.db;
    if (!db) return;

    const batch = parseInt(process.env.SENTIMENT_INTAKE_BATCH || '50', 10);
    const maxSymbols = parseInt(process.env.SENTIMENT_INTAKE_MAX_SYMBOLS_PER_TWEET || '3', 10);
    const tweetsCollection = db.collection('twitter_results');

    const processedDocs = await SentimentProcessingModel.find(
      { processed: true },
      { tweetId: 1 }
    ).lean();
    const processedIds = new Set(processedDocs.map(d => d.tweetId));

    const tweets = await tweetsCollection
      .find({ tweetId: { $nin: [...processedIds] } })
      .sort({ createdAt: 1 })
      .limit(batch)
      .toArray();

    if (!tweets.length) return;

    for (const tw of tweets) {
      const tweetId = tw.tweetId;
      try {
        const text = tw.text || '';
        const symbols = extractSymbols(text, maxSymbols);

        await SentimentProcessingModel.updateOne(
          { tweetId },
          { $set: { processed: true, processedAt: new Date(), symbols: symbols || [] } },
          { upsert: true }
        );

        if (!symbols.length) {
          this.stats.tweetsProcessed++;
          continue;
        }

        const baseSentiment = mockSentimentEngine.analyze(text);
        const weighting = sentimentWeightingService.compute({
          baseScore: baseSentiment.score,
          baseConfidence: baseSentiment.confidence,
          tweetCreatedAt: tw.tweetedAt ? new Date(tw.tweetedAt) : new Date(),
        });

        for (const symbol of symbols) {
          await SentimentEventModel.updateOne(
            { tweetId, symbol },
            {
              $setOnInsert: { tweetId, symbol, tweetCreatedAt: tw.tweetedAt ? new Date(tw.tweetedAt) : new Date(), authorHandle: tw.author?.username || tw.username },
              $set: { baseLabel: baseSentiment.label, baseScore: baseSentiment.score, baseConfidence: baseSentiment.confidence, weightedScore: weighting.weightedScore, weightedConfidence: weighting.weightedConfidence, processedAt: new Date(), processingVersion: PROCESSING_VERSION },
            },
            { upsert: true }
          );
          this.stats.eventsCreated++;
        }
        this.stats.tweetsProcessed++;
      } catch (err: any) {
        await SentimentProcessingModel.updateOne(
          { tweetId },
          { $set: { lastError: err.message }, $inc: { errorCount: 1 } },
          { upsert: true }
        ).catch(() => {});
        this.stats.errorsCount++;
      }
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Singleton instance
let workerInstance: SentimentIntakeWorker | null = null;

/**
 * Get or create worker instance
 */
export function getSentimentIntakeWorker(): SentimentIntakeWorker {
  if (!workerInstance) {
    workerInstance = new SentimentIntakeWorker();
  }
  return workerInstance;
}

/**
 * Start the intake worker (call from bootstrap)
 */
export async function startSentimentIntakeWorker(): Promise<void> {
  const enabled = process.env.SENTIMENT_INTAKE_ENABLED === 'true';
  
  if (!enabled) {
    console.log('[SentimentIntake] Worker disabled (SENTIMENT_INTAKE_ENABLED != true)');
    return;
  }

  const worker = getSentimentIntakeWorker();
  
  // Start in background (don't await)
  worker.start().catch(err => {
    console.error('[SentimentIntake] Worker crashed:', err);
  });
}
