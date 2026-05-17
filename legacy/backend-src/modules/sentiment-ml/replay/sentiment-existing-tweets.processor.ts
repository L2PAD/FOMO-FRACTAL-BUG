/**
 * Sentiment Existing Tweets Processor
 * =====================================
 * 
 * Process existing parsed tweets through sentiment pipeline.
 * Uses tweets from user_twitter_parsed_tweets collection.
 * 
 * This is a SAFE way to test the full pipeline with real historical data.
 */

import { SentimentDirSampleModel, SentimentWindow } from '../dataset/sentiment-dir-sample.model.js';

interface ProcessResult {
  processed: number;
  skipped: number;
  errors: number;
  bySymbol: Record<string, number>;
}

export class SentimentExistingTweetsProcessor {
  /**
   * Get symbol from tweet text
   */
  private extractSymbol(text: string): string | null {
    const symbols = [
      'BTC', 'ETH', 'SOL', 'XRP', 'BNB',
      'ADA', 'AVAX', 'DOGE', 'LINK', 'MATIC',
      'DOT', 'LTC', 'TRX', 'UNI', 'ATOM',
      'APT', 'ARB', 'OP', 'INJ', 'SUI'
    ];
    
    const upperText = text.toUpperCase();
    
    for (const sym of symbols) {
      // Check for $BTC or BTC patterns
      if (upperText.includes(`$${sym}`) || 
          upperText.includes(` ${sym} `) ||
          upperText.includes(`${sym}/`) ||
          upperText.startsWith(`${sym} `)) {
        return sym;
      }
    }
    
    // Check for Bitcoin/Ethereum mentions
    if (upperText.includes('BITCOIN')) return 'BTC';
    if (upperText.includes('ETHEREUM')) return 'ETH';
    if (upperText.includes('SOLANA')) return 'SOL';
    
    return null;
  }

  /**
   * Process a batch of existing tweets and create sentiment events
   */
  async processExistingTweets(db: any): Promise<ProcessResult> {
    const result: ProcessResult = {
      processed: 0,
      skipped: 0,
      errors: 0,
      bySymbol: {},
    };

    try {
      // Get all parsed tweets
      const tweets = await db.collection('user_twitter_parsed_tweets')
        .find({})
        .sort({ tweetedAt: 1 })
        .toArray();

      console.log(`[ExistingTweets] Found ${tweets.length} tweets to process`);

      for (const tweet of tweets) {
        try {
          // Extract symbol
          const symbol = this.extractSymbol(tweet.text || '');
          
          if (!symbol) {
            result.skipped++;
            continue;
          }

          // Create sentiment event
          const event = {
            symbol,
            tweetId: tweet.tweetId,
            authorId: tweet.author?.id || tweet.username,
            authorHandle: tweet.username,
            tweetCreatedAt: new Date(tweet.tweetedAt),
            baseScore: 0.5 + (Math.random() - 0.5) * 0.3, // Mock score for now
            baseLabel: 'NEUTRAL',
            baseConfidence: 0.5 + Math.random() * 0.3,
            weightedScore: 0.5 + (Math.random() - 0.5) * 0.4,
            weightedConfidence: 0.5 + Math.random() * 0.4,
            connectionsAvailable: false,
            processedAt: new Date(),
            processingVersion: 'v2.0-replay',
            createdAt: new Date(),
            updatedAt: new Date(),
          };

          // Upsert to avoid duplicates
          await db.collection('sentiment_events').updateOne(
            { tweetId: tweet.tweetId },
            { $set: event },
            { upsert: true }
          );

          result.processed++;
          result.bySymbol[symbol] = (result.bySymbol[symbol] || 0) + 1;

        } catch (err: any) {
          result.errors++;
          console.error(`[ExistingTweets] Error processing tweet ${tweet.tweetId}:`, err.message);
        }
      }

      console.log(`[ExistingTweets] Completed | processed: ${result.processed} | skipped: ${result.skipped} | errors: ${result.errors}`);

    } catch (err: any) {
      console.error('[ExistingTweets] Fatal error:', err.message);
    }

    return result;
  }
}

export function getExistingTweetsProcessor(): SentimentExistingTweetsProcessor {
  return new SentimentExistingTweetsProcessor();
}

console.log('[Sentiment-ML] Existing Tweets Processor loaded');
