/**
 * Sentiment Guard Routes
 * ========================
 * 
 * BLOCK 10.2: Admin API for parser health guard.
 * 
 * Endpoints:
 * - GET /guards/parser-health — current state
 * - POST /guards/parser-health/run — manual check
 * - POST /guards/kill-switch — manual kill switch
 */

import fp from 'fastify-plugin';
import type { FastifyInstance, FastifyRequest } from 'fastify';
import { getSentimentParserHealthGuard } from './sentiment_parser_health_guard.service.js';
import { getSentimentDriftService } from '../drift/sentiment_drift.service.js';

async function sentimentGuardRoutes(app: FastifyInstance): Promise<void> {
  const guard = getSentimentParserHealthGuard();
  const drift = getSentimentDriftService();

  /**
   * GET /guards/parser-health — Current parser health state
   */
  app.get('/parser-health', async () => {
    const state = await guard.getState();
    const isWorkersAllowed = await guard.isWorkersAllowed();
    const isTrainingAllowed = await guard.isTrainingAllowed();
    const confidenceModifier = await guard.getConfidenceModifier();

    return {
      ok: true,
      state: state || { status: 'UNKNOWN', reasons: [] },
      flags: {
        isWorkersAllowed,
        isTrainingAllowed,
        confidenceModifier,
      },
    };
  });

  /**
   * POST /guards/parser-health/run — Trigger manual health check
   */
  app.post('/parser-health/run', async () => {
    const result = await guard.runCheck(new Date());
    return {
      ok: true,
      result,
    };
  });

  /**
   * POST /guards/kill-switch — Manual kill switch control
   */
  app.post('/kill-switch', async (req: FastifyRequest<{
    Body: { enabled: boolean; note?: string }
  }>) => {
    const body = req.body || {} as any;
    const enabled = Boolean(body.enabled);
    const note = body.note || undefined;

    await guard.setKillSwitch(enabled, note);
    
    return {
      ok: true,
      killSwitchEnabled: enabled,
      note,
    };
  });

  /**
   * GET /drift/latest — Latest drift result
   */
  app.get('/drift/latest', async (req: FastifyRequest<{
    Querystring: { window?: string }
  }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const result = await drift.getLatest(window);
    
    return {
      ok: true,
      window,
      result: result || null,
    };
  });

  /**
   * POST /drift/run — Trigger manual drift check
   */
  app.post('/drift/run', async (req: FastifyRequest<{
    Body: { window?: string }
  }>) => {
    const body = req.body || {} as any;
    const window = (body.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    
    const result = await drift.runOnce(window, new Date());
    
    return {
      ok: true,
      window,
      result,
    };
  });

  /**
   * GET /drift/history — Drift history
   */
  app.get('/drift/history', async (req: FastifyRequest<{
    Querystring: { window?: string; days?: string }
  }>) => {
    const window = (req.query.window?.toUpperCase() || '24H') as '24H' | '7D' | '30D';
    const days = parseInt(req.query.days || '30', 10);
    
    const history = await drift.getHistory(window, days);
    
    return {
      ok: true,
      window,
      days,
      count: history.length,
      history,
    };
  });

  /**
   * GET /status/full — Combined status for admin dashboard
   */
  app.get('/status/full', async () => {
    const guardState = await guard.getState();
    const driftResult = await drift.getLatest('24H');
    const isWorkersAllowed = await guard.isWorkersAllowed();
    const isTrainingAllowed = await guard.isTrainingAllowed();
    const confidenceModifier = await guard.getConfidenceModifier();

    // Combined reliability score
    let reliabilityScore = 1.0;
    let reliabilityStatus: 'OK' | 'WARN' | 'DEGRADED' | 'CRITICAL' = 'OK';

    // Factor in guard state
    if (guardState?.status === 'CRITICAL') {
      reliabilityScore *= 0.3;
      reliabilityStatus = 'CRITICAL';
    } else if (guardState?.status === 'DEGRADED') {
      reliabilityScore *= 0.6;
      reliabilityStatus = 'DEGRADED';
    } else if (guardState?.status === 'WARN') {
      reliabilityScore *= 0.8;
      reliabilityStatus = 'WARN';
    }

    // Factor in drift
    if (driftResult?.status === 'CRITICAL') {
      reliabilityScore *= 0.4;
      if (reliabilityStatus === 'OK') reliabilityStatus = 'CRITICAL';
    } else if (driftResult?.status === 'DEGRADED') {
      reliabilityScore *= 0.7;
      if (reliabilityStatus === 'OK') reliabilityStatus = 'DEGRADED';
    } else if (driftResult?.status === 'WARN') {
      reliabilityScore *= 0.9;
      if (reliabilityStatus === 'OK') reliabilityStatus = 'WARN';
    }

    return {
      ok: true,
      reliability: {
        score: reliabilityScore,
        status: reliabilityStatus,
        confidenceModifier,
      },
      guard: {
        status: guardState?.status || 'UNKNOWN',
        reasons: guardState?.reasons || [],
        isKillSwitchOn: guardState?.isKillSwitchOn || false,
        isWorkersAllowed,
        isTrainingAllowed,
        updatedAt: guardState?.updatedAt || null,
      },
      drift: {
        status: driftResult?.status || 'UNKNOWN',
        score: driftResult?.driftScore || 0,
        nLive: driftResult?.nLive || 0,
        asOf: driftResult?.asOf || null,
      },
    };
  });
}

export default fp(sentimentGuardRoutes, {
  name: 'sentiment-guard-routes',
  fastify: '4.x',
});

export { sentimentGuardRoutes };
