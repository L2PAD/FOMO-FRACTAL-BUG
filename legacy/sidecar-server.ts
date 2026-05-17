/**
 * FOMO Fractal Sidecar — minimal Node.js entry point.
 * Hosts ONLY the Fractal Engine subsystem (Replay/Synthetic/Hybrid/Overlay)
 * on port 8003.  Python FastAPI (port 8001) is the canonical runtime for
 * everything else and proxies fractal v2.1 calls here.
 */

// Load .env from main backend
import 'dotenv/config';
import { readFileSync } from 'fs';
try {
  const envContent = readFileSync('/app/backend/.env', 'utf8');
  for (const line of envContent.split('\n')) {
    if (line.startsWith('#') || !line.includes('=')) continue;
    const eqIdx = line.indexOf('=');
    const key = line.slice(0, eqIdx).trim();
    const val = line.slice(eqIdx + 1).trim().replace(/^["']|["']$/g, '');
    if (!process.env[key]) process.env[key] = val;
  }
} catch { /* fall through */ }

// Legacy Node code expects MONGODB_URI; Python uses MONGO_URL.
if (!process.env.MONGODB_URI && process.env.MONGO_URL) {
  process.env.MONGODB_URI = process.env.MONGO_URL;
}
// Legacy expects PORT — we override with NODE_SIDECAR_PORT
process.env.PORT = process.env.NODE_SIDECAR_PORT || '8003';

import Fastify from 'fastify';
import cors from '@fastify/cors';
import { connectMongo } from './backend-src/db/mongoose.js';

const PORT = parseInt(process.env.NODE_SIDECAR_PORT || '8003', 10);
const HOST = process.env.NODE_SIDECAR_HOST || '127.0.0.1';

async function main() {
  console.log('[Sidecar] Starting Fractal sidecar...');

  // Connect to Mongo (best-effort)
  try {
    await connectMongo();
    console.log('[Sidecar] Mongo connected');
  } catch (e) {
    console.error('[Sidecar] Mongo connect failed (continuing):', (e as Error).message);
  }

  const app = Fastify({
    logger: { level: 'warn' },
    bodyLimit: 50 * 1024 * 1024,
  });

  await app.register(cors, { origin: true });

  // ── Health check ────────────────────────────────────────────────
  app.get('/healthz', async () => ({ ok: true, sidecar: 'fractal', port: PORT }));

  // ── Mount Fractal Engine plugin (best-effort, isolate failures) ──
  try {
    const { bootFractalEngine } = await import('./backend-src/fractal-engine-boot.js');
    await bootFractalEngine(app);
    console.log('[Sidecar] Fractal engine plugin mounted');
  } catch (e: any) {
    console.error('[Sidecar] Fractal engine plugin FAILED:', e?.message || e);
    console.error(e?.stack);
    // Continue — we'll try individual module mounts as fallback
  }

  await app.listen({ port: PORT, host: HOST });
  console.log(`[Sidecar] Listening on http://${HOST}:${PORT}`);
}

main().catch((e) => {
  console.error('[Sidecar] FATAL:', e);
  process.exit(1);
});
