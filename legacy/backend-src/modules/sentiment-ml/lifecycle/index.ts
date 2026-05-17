/**
 * Sentiment ML Lifecycle Module
 * ==============================
 * 
 * BLOCK 5 + S4: Complete lifecycle management for Sentiment ML.
 * 
 * Components:
 * - Registry: Active/Shadow model tracking
 * - Guards: Kill switch, promotion lock, time-based lock
 * - Auto-Promotion: Sustained lift + Capital gates → ML active
 * - Auto-Rollback: Degradation + Capital triggers → RULE active
 * - Capital Window: Rolling performance metrics
 * - Capital Guard: Promotion/Rollback gates
 * - Audit: Event logging
 */

export * from './sentiment_model_events.model.js';
export * from './sentiment_guards.service.js';
export * from './sentiment_model_registry.service.js';
export * from './sentiment_shadow_window.service.js';
export * from './sentiment_auto_promotion.service.js';
export * from './sentiment_auto_rollback.service.js';
export * from './sentiment_capital_window.service.js';
export * from './sentiment_capital_guard.js';
export * from './sentiment_lifecycle.routes.js';

console.log('[Sentiment-ML] Lifecycle module loaded (BLOCK 5 + S4)');
