/**
 * Sentiment Shadow Module Index
 * ==============================
 * 
 * BLOCK 9: Shadow Mode for 24H sentiment predictions.
 * 
 * Exports:
 * - Model: SentimentShadowDecisionModel
 * - Services: SentimentShadowService, SentimentShadowAnalyticsService
 * - Routes: sentimentShadowRoutes
 */

export { 
  SentimentShadowDecisionModel, 
  getSentimentShadowDecisionModel,
  type SentimentShadowDecision,
} from './sentiment.shadow.model.js';

export { 
  SentimentShadowService, 
  getSentimentShadowService,
  type RecordShadowParams,
} from './sentiment.shadow.service.js';

export { 
  SentimentShadowAnalyticsService, 
  getSentimentShadowAnalyticsService,
  type ShadowSummary,
  type DisagreementDetail,
} from './sentiment.shadow.analytics.service.js';

// Routes (both default and named export for flexibility)
export { default as sentimentShadowRoutesPlugin, sentimentShadowRoutes } from './sentiment.shadow.routes.js';

console.log('[Sentiment-ML] Shadow module loaded (BLOCK 9)');
