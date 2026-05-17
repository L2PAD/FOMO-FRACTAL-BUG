/**
 * CEX Registry Routes — Phase A1.2
 * ==================================
 *
 * POST /cex/registry/import   — Bulk import addresses
 * GET  /cex/registry/stats    — Registry statistics
 * GET  /cex/registry/exchanges — List exchanges
 * POST /cex/registry/import-datasets — Import from /datasets/cex/ folder
 */

import { FastifyInstance, FastifyRequest } from 'fastify';
import { CexRegistryService, ImportRequest } from './cex_registry.service';
import * as fs from 'fs';
import * as path from 'path';

const svc = new CexRegistryService();

export async function cexRegistryRoutes(fastify: FastifyInstance): Promise<void> {
  /**
   * POST /cex/registry/import
   */
  fastify.post('/import', async (request: FastifyRequest<{ Body: ImportRequest }>) => {
    try {
      const body = request.body;
      if (!body?.entityId || !body?.addresses?.length) {
        return { ok: false, error: 'MISSING_FIELDS', message: 'entityId and addresses[] required' };
      }
      const report = await svc.bulkImport({
        entityId: body.entityId,
        entityName: body.entityName || body.entityId,
        chainId: body.chainId || 1,
        addresses: body.addresses,
      });
      return { ok: true, report };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  /**
   * GET /cex/registry/stats
   */
  fastify.get('/stats', async (request: FastifyRequest<{
    Querystring: { chainId?: string };
  }>) => {
    try {
      const chainId = request.query.chainId ? Number(request.query.chainId) : undefined;
      const stats = await svc.getStats(chainId);
      return { ok: true, ...stats };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  /**
   * GET /cex/registry/exchanges
   */
  fastify.get('/exchanges', async () => {
    try {
      const exchanges = await svc.listExchanges();
      return { ok: true, exchanges };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  /**
   * POST /cex/registry/import-datasets
   * Loads all JSON files from /datasets/cex/ and imports them
   */
  fastify.post('/import-datasets', async () => {
    try {
      const datasetsDir = path.resolve(process.cwd(), 'datasets', 'cex');
      if (!fs.existsSync(datasetsDir)) {
        return { ok: false, error: 'DATASETS_DIR_NOT_FOUND', path: datasetsDir };
      }

      const files = fs.readdirSync(datasetsDir).filter(f => f.endsWith('.json'));
      const results = [];

      for (const file of files) {
        const filePath = path.join(datasetsDir, file);
        const raw = fs.readFileSync(filePath, 'utf8');
        const data = JSON.parse(raw);

        const report = await svc.bulkImport({
          entityId: data.entityId,
          entityName: data.entityName || data.entityId,
          chainId: data.chainId || 1,
          addresses: data.addresses || [],
        });

        results.push({
          file,
          ...report,
        });
      }

      const totalInserted = results.reduce((s, r) => s + r.inserted, 0);
      const totalUpdated = results.reduce((s, r) => s + r.updated, 0);
      const totalAddresses = results.reduce((s, r) => s + r.total, 0);

      return {
        ok: true,
        filesProcessed: files.length,
        totalInserted,
        totalUpdated,
        totalAddresses,
        reports: results,
      };
    } catch (e: any) {
      return { ok: false, error: e.message };
    }
  });

  console.log('[CEX Registry Routes] Registered');
}
