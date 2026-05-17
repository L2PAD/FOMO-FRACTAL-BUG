/**
 * Exchange Reliability Routes
 * ============================
 * 
 * EX-S1: Admin API for Exchange reliability monitoring.
 * 
 * Endpoints:
 * - GET /status — full URI status with components
 * - GET /actions — just the current actions
 */

import fp from 'fastify-plugin';
import type { FastifyInstance } from 'fastify';
import { getExchangeReliabilityService } from './exchange-reliability.service.js';
import { EX_URI_THRESHOLDS, EX_URI_WEIGHTS } from './exchange-reliability.types.js';

async function exchangeReliabilityRoutes(app: FastifyInstance): Promise<void> {
  const reliabilityService = getExchangeReliabilityService();

  /**
   * GET /status — Full reliability status
   */
  app.get('/status', async () => {
    const status = await reliabilityService.computeStatus();

    return {
      ok: true,
      reliability: {
        score: status.uriScore,
        scoreFormatted: `${(status.uriScore * 100).toFixed(1)}%`,
        level: status.level,
        components: {
          dataHealth: `${(status.components.dataHealth * 100).toFixed(0)}%`,
          driftHealth: `${(status.components.driftHealth * 100).toFixed(0)}%`,
          capitalHealth: `${(status.components.capitalHealth * 100).toFixed(0)}%`,
          calibrationHealth: `${(status.components.calibrationHealth * 100).toFixed(0)}%`,
        },
        componentsRaw: status.components,
        reasons: status.reasons,
        actions: status.actions,
        asOf: status.asOf,
      },
      thresholds: {
        OK: `≥${EX_URI_THRESHOLDS.OK * 100}%`,
        WARN: `${EX_URI_THRESHOLDS.WARN * 100}-${EX_URI_THRESHOLDS.OK * 100}%`,
        DEGRADED: `${EX_URI_THRESHOLDS.DEGRADED * 100}-${EX_URI_THRESHOLDS.WARN * 100}%`,
        CRITICAL: `<${EX_URI_THRESHOLDS.DEGRADED * 100}%`,
      },
      weights: EX_URI_WEIGHTS,
    };
  });

  /**
   * GET /actions — Just current actions
   */
  app.get('/actions', async () => {
    const status = await reliabilityService.computeStatus();

    return {
      ok: true,
      level: status.level,
      actions: status.actions,
      reasons: status.reasons,
      asOf: status.asOf,
    };
  });

  /**
   * GET /components — Detailed breakdown of each component
   */
  app.get('/components', async () => {
    const status = await reliabilityService.computeStatus();

    return {
      ok: true,
      dataHealth: {
        score: `${(status.components.dataHealth * 100).toFixed(0)}%`,
        weight: EX_URI_WEIGHTS.dataHealth,
        contribution: (status.components.dataHealth * EX_URI_WEIGHTS.dataHealth * 100).toFixed(1) + '%',
        raw: status.raw?.data,
      },
      driftHealth: {
        score: `${(status.components.driftHealth * 100).toFixed(0)}%`,
        weight: EX_URI_WEIGHTS.driftHealth,
        contribution: (status.components.driftHealth * EX_URI_WEIGHTS.driftHealth * 100).toFixed(1) + '%',
        raw: status.raw?.drift,
      },
      capitalHealth: {
        score: `${(status.components.capitalHealth * 100).toFixed(0)}%`,
        weight: EX_URI_WEIGHTS.capitalHealth,
        contribution: (status.components.capitalHealth * EX_URI_WEIGHTS.capitalHealth * 100).toFixed(1) + '%',
        raw: status.raw?.capital,
      },
      calibrationHealth: {
        score: `${(status.components.calibrationHealth * 100).toFixed(0)}%`,
        weight: EX_URI_WEIGHTS.calibrationHealth,
        contribution: (status.components.calibrationHealth * EX_URI_WEIGHTS.calibrationHealth * 100).toFixed(1) + '%',
        raw: status.raw?.calibration,
      },
      totalScore: `${(status.uriScore * 100).toFixed(1)}%`,
      level: status.level,
    };
  });
}

export default fp(exchangeReliabilityRoutes, {
  name: 'exchange-reliability-routes',
  fastify: '4.x',
});

export { exchangeReliabilityRoutes };
