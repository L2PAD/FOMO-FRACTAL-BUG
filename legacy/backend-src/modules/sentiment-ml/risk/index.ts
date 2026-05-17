/**
 * Sentiment ML Risk Module
 * =========================
 * 
 * BLOCK 6: Capital & Risk Layer.
 * 
 * Components:
 * - Trade Model: Paper trades storage
 * - Position State: Active position tracking
 * - Risk Guard: Exposure/concurrency/cooldown guards
 * - Trade Builder: Creates trades from samples
 * - Trade Perf: Equity/MaxDD/Sharpe metrics
 * - Risk Routes: Admin API
 */

export * from './sent_trade.model.js';
export * from './sent_position_state.model.js';
export * from './sent_risk_guard.service.js';
export * from './sent_trade_builder.service.js';
export * from './sent_trade_perf.service.js';
export * from './sent_risk.routes.js';

console.log('[Sentiment-ML] Risk module loaded (BLOCK 6)');
