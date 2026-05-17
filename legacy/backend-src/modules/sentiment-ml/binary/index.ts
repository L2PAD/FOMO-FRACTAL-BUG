/**
 * Sentiment Binary Module Index
 * ==============================
 * 
 * BLOCK 8: Binary ML Layer exports.
 */

// Contracts
export * from '../contracts/sentiment-ml.types.js';

// Feature extraction
export * from './sentiment.binary.feature-extractor.js';

// Models
export * from './models/index.js';

// Training
export * from './sentiment.binary.trainer.js';

// Inference
export * from './sentiment.binary.inference.service.js';

// Routes
export { default as sentimentBinaryAdminRoutesPlugin, sentimentBinaryAdminRoutes } from './sentiment.binary.admin.routes.js';

console.log('[Sentiment-ML] Binary module loaded (BLOCK 8)');
