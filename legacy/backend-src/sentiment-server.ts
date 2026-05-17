/**
 * Sentiment API — Standalone Server
 * ==================================
 * Выделенный сервер только для Sentiment API.
 * Порт: 8005
 *
 * Запуск: npx tsx src/sentiment-server.ts
 */

import 'dotenv/config';
import Fastify from 'fastify';
import cors from '@fastify/cors';
import { registerSentimentV1Routes } from './modules/sentiment/v1.routes.js';
import { connectMongo } from './db/mongoose.js';

const PORT = 8005;

async function start() {
  const app = Fastify({
    logger: false,
    bodyLimit: 1048576,
  });

  await app.register(cors, { origin: true });

  // Connect to MongoDB (for API keys + config)
  try {
    await connectMongo();
    console.log('[Sentiment] MongoDB connected');
  } catch (err) {
    console.error('[Sentiment] MongoDB connection failed:', err);
  }

  // Register sentiment routes
  await app.register(async (fastify) => {
    await registerSentimentV1Routes(fastify);
  });

  // Root health
  app.get('/', async () => ({
    service: 'sentiment-api',
    version: '2.0.0',
    port: PORT,
    status: 'running',
  }));

  await app.listen({ port: PORT, host: '0.0.0.0' });
  console.log(`[Sentiment] Standalone server running on port ${PORT}`);
  console.log(`[Sentiment] Health: http://localhost:${PORT}/api/v1/sentiment/health`);
}

start().catch((err) => {
  console.error('[Sentiment] Failed to start:', err);
  process.exit(1);
});
