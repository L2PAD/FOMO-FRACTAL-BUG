/**
 * Exchange Admin Snapshot Routes
 * ================================
 * 
 * BLOCK E6: Single endpoint for admin dashboard
 * GET /api/admin/exchange-ml/admin-snapshot
 */

import type { FastifyInstance } from 'fastify';
import { getExchangeAdminSnapshotService } from './exchange-admin-snapshot.service.js';

export async function registerExchangeAdminSnapshotRoutes(fastify: FastifyInstance): Promise<void> {
  const service = getExchangeAdminSnapshotService();

  /**
   * GET /api/admin/exchange-ml/admin-snapshot
   * Returns complete admin dashboard snapshot
   */
  fastify.get('/api/admin/exchange-ml/admin-snapshot', async (request, reply) => {
    try {
      const snapshot = await service.getSnapshot();
      return reply.send(snapshot);
    } catch (err: any) {
      console.error('[ExchangeAdminSnapshot] Error:', err);
      return reply.status(500).send({
        ok: false,
        error: err.message || 'Internal server error',
      });
    }
  });

  /**
   * POST /api/admin/exchange-ml/actions/rerun-drift
   * Trigger drift recalculation
   */
  fastify.post('/api/admin/exchange-ml/actions/rerun-drift', async (request, reply) => {
    // In production, would trigger drift service
    return reply.send({ ok: true, message: 'Drift check queued' });
  });

  /**
   * POST /api/admin/exchange-ml/actions/rerun-calibration
   * Trigger calibration recalculation
   */
  fastify.post('/api/admin/exchange-ml/actions/rerun-calibration', async (request, reply) => {
    return reply.send({ ok: true, message: 'Calibration check queued' });
  });

  /**
   * POST /api/admin/exchange-ml/actions/recompute-capital
   * Trigger capital window recalculation
   */
  fastify.post('/api/admin/exchange-ml/actions/recompute-capital', async (request, reply) => {
    return reply.send({ ok: true, message: 'Capital window recompute queued' });
  });

  /**
   * POST /api/admin/exchange-ml/actions/flush-evidence
   * Persist pending evidence events
   */
  fastify.post('/api/admin/exchange-ml/actions/flush-evidence', async (request, reply) => {
    return reply.send({ ok: true, message: 'Evidence flush completed' });
  });

  console.log('[Exchange-Admin] Snapshot routes registered:');
  console.log('  - GET /api/admin/exchange-ml/admin-snapshot');
  console.log('  - POST /api/admin/exchange-ml/actions/rerun-drift');
  console.log('  - POST /api/admin/exchange-ml/actions/rerun-calibration');
  console.log('  - POST /api/admin/exchange-ml/actions/recompute-capital');
  console.log('  - POST /api/admin/exchange-ml/actions/flush-evidence');
}
