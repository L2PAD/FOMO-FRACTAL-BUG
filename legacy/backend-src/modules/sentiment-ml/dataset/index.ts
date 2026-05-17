/**
 * Sentiment Dataset Module Index
 * ================================
 * 
 * BLOCK 6: Forward-only dataset accumulator exports.
 */

export * from './sentiment-dir-sample.model.js';
export * from './sentiment-dataset-labels.js';
export * from './sentiment-price.adapter.js';
export * from './sentiment-dataset.accumulator.js';
export * from './sentiment-dataset-finalize.job.js';
export * from './sentiment-dataset-stats.service.js';

// Routes - export default plugin and named function
export { default as sentimentDatasetRoutesPlugin, sentimentDatasetRoutes } from './sentiment-dataset.routes.js';
