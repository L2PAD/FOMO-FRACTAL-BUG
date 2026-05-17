/**
 * Sentiment-ML Module Index
 * =========================
 * 
 * Entry point для нового Sentiment-ML модуля с архитектурой как у Exchange.
 * 
 * БЛОК 1: ConnectionsAdapter → Sentiment Pipeline
 * БЛОК 2: Intake Worker + Symbol Extraction + sentiment_events
 * БЛОК 3: Weighted Sentiment Engine
 * БЛОК 4: Aggregation Engine (24H/7D/30D)
 * 
 * ПРИНЦИП:
 * - Изолированный модуль
 * - Connections через порт/адаптер
 * - Graceful fallback при отключённом Connections
 * - Background workers для обработки твитов и агрегации
 * - Deterministic weighting (защита от манипуляций)
 * 
 * ENV VARIABLES:
 * - CONNECTIONS_ENABLED=true/false — включить Connections enrichment
 * - SENTIMENT_ML_ENABLED=true/false — включить новый Sentiment-ML модуль
 * - SENTIMENT_INTAKE_ENABLED=true/false — включить intake worker
 * - SENTIMENT_INTAKE_POLL_MS=2500 — интервал polling
 * - SENTIMENT_INTAKE_BATCH=50 — размер batch
 * - SENTIMENT_AGG_ENABLED=true/false — включить aggregation worker
 * - SENTIMENT_AGG_INTERVAL_MS=60000 — интервал агрегации
 */

import { MongoClient } from 'mongodb';
import { ConnectionsPort } from './ports/connections.port.js';
import { ConnectionsAdapter } from './adapters/connections.adapter.js';
import { MockConnectionsAdapter } from './adapters/connections.mock.adapter.js';
import { SentimentEnrichmentService } from './services/sentiment-enrichment.service.js';

// Singleton instances
let connectionsAdapter: ConnectionsPort | null = null;
let enrichmentService: SentimentEnrichmentService | null = null;
let initialized = false;

/**
 * Инициализировать Sentiment-ML модуль
 */
export function initSentimentML(mongoClient: MongoClient): void {
  if (initialized) {
    console.log('[Sentiment-ML] Already initialized');
    return;
  }

  const connectionsEnabled = process.env.CONNECTIONS_ENABLED === 'true';

  // Выбираем адаптер в зависимости от конфигурации
  if (connectionsEnabled) {
    connectionsAdapter = new ConnectionsAdapter(mongoClient);
    console.log('[Sentiment-ML] Using REAL ConnectionsAdapter');
  } else {
    connectionsAdapter = new MockConnectionsAdapter();
    console.log('[Sentiment-ML] Using MockConnectionsAdapter (CONNECTIONS_ENABLED=false)');
  }

  // Создаём enrichment service
  enrichmentService = new SentimentEnrichmentService(connectionsAdapter);

  initialized = true;
  console.log('[Sentiment-ML] Module initialized (Block 1-4)');
}

/**
 * Получить ConnectionsPort для прямого использования
 */
export function getConnectionsPort(): ConnectionsPort {
  if (!connectionsAdapter) {
    throw new Error('[Sentiment-ML] Module not initialized. Call initSentimentML() first.');
  }
  return connectionsAdapter;
}

/**
 * Получить SentimentEnrichmentService
 */
export function getSentimentEnrichmentService(): SentimentEnrichmentService {
  if (!enrichmentService) {
    throw new Error('[Sentiment-ML] Module not initialized. Call initSentimentML() first.');
  }
  return enrichmentService;
}

/**
 * Проверить инициализацию модуля
 */
export function isSentimentMLInitialized(): boolean {
  return initialized;
}

/**
 * Получить статус модуля
 */
export function getSentimentMLStatus(): {
  initialized: boolean;
  connectionsEnabled: boolean;
  connectionsAvailable: boolean;
  enrichmentStats: any;
  intakeEnabled: boolean;
  aggEnabled: boolean;
} {
  return {
    initialized,
    connectionsEnabled: process.env.CONNECTIONS_ENABLED === 'true',
    connectionsAvailable: connectionsAdapter?.isAvailable() ?? false,
    enrichmentStats: enrichmentService?.getStats() ?? null,
    intakeEnabled: process.env.SENTIMENT_INTAKE_ENABLED === 'true',
    aggEnabled: process.env.SENTIMENT_AGG_ENABLED === 'true',
  };
}

// Экспорт типов и интерфейсов
export * from './ports/connections.port.js';
export * from './adapters/connections.adapter.js';
export * from './adapters/connections.mock.adapter.js';
export * from './services/sentiment-enrichment.service.js';

// Block 2 exports
export * from './storage/sentiment-event.model.js';
export * from './storage/sentiment-processing.model.js';
export * from './runtime/symbol-extractor.js';
export * from './engines/mock-sentiment.engine.js';
export { getSentimentIntakeWorker, startSentimentIntakeWorker } from './runtime/sentiment-intake.worker.js';

// Block 3 exports
export * from './engines/sentiment-weighting.service.js';

// Block 4 exports
export * from './storage/sentiment-aggregate.model.js';
export * from './services/sentiment-aggregation.service.js';
export * from './config/top20-symbols.js';
export { getSentimentAggregateWorker, startSentimentAggregateWorker } from './runtime/sentiment-aggregate.worker.js';

// Block 6 exports (Dataset Accumulator)
export * from './dataset/index.js';
