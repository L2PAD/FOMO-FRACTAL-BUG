/**
 * Sentiment Reliability Routes
 * ==============================
 * 
 * BLOCK S1: Admin API for Unified Reliability Index.
 * 
 * Endpoints:
 * - GET /status — current reliability status
 * - POST /run — force recalculate
 */

import fp from 'fastify-plugin';
import type { FastifyInstance } from 'fastify';
import { getSentimentReliabilityService } from './sentiment-reliability.service.js';
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load module manifest
let moduleManifest: any = null;
try {
  const manifestPath = join(__dirname, '../module_manifest.json');
  moduleManifest = JSON.parse(readFileSync(manifestPath, 'utf-8'));
} catch (err) {
  console.warn('[Sentiment] Failed to load module manifest:', err);
  moduleManifest = { version: '1.0.0', frozen: false, moduleName: 'sentiment-ml' };
}

async function sentimentReliabilityRoutes(app: FastifyInstance): Promise<void> {
  const reliability = getSentimentReliabilityService();

  /**
   * GET /status — Current reliability status
   */
  app.get('/status', async () => {
    const status = await reliability.computeStatus();
    
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
        OK: '≥75%',
        WARN: '60-75%',
        DEGRADED: '40-60%',
        CRITICAL: '<40%',
      },
    };
  });

  /**
   * POST /run — Force recalculate reliability
   */
  app.post('/run', async () => {
    const status = await reliability.computeStatus();
    
    return {
      ok: true,
      message: 'Reliability recalculated',
      reliability: {
        score: status.uriScore,
        level: status.level,
        components: status.components,
        reasons: status.reasons,
        actions: status.actions,
      },
    };
  });

  /**
   * GET /actions — Get current actions only
   */
  app.get('/actions', async () => {
    const status = await reliability.computeStatus();
    
    return {
      ok: true,
      level: status.level,
      actions: status.actions,
      summary: {
        canRunWorkers: !status.actions.workersBlocked,
        canTrain: !status.actions.trainingBlocked,
        confidenceMultiplier: `${(status.actions.confidenceMultiplier * 100).toFixed(0)}%`,
        sizeMultiplier: `${(status.actions.sizeMultiplier * 100).toFixed(0)}%`,
      },
    };
  });

  /**
   * GET /module-manifest — Get frozen module manifest
   */
  app.get('/module-manifest', async () => {
    return {
      ok: true,
      manifest: moduleManifest,
    };
  });
}

export default fp(sentimentReliabilityRoutes, {
  name: 'sentiment-reliability-routes',
  fastify: '4.x',
});

export { sentimentReliabilityRoutes };
