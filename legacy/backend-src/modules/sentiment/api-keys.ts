/**
 * Sentiment API Keys — MongoDB-backed key management
 * ===================================================
 * Generates, validates, and revokes API keys for external access.
 */

import { randomBytes, createHash } from 'crypto';
import { getDb } from '../../db/mongodb.js';

const COLLECTION = 'sentiment_api_keys';

export interface ApiKeyDoc {
  key_hash: string;
  prefix: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  requests: number;
  active: boolean;
}

function hashKey(key: string): string {
  return createHash('sha256').update(key).digest('hex');
}

/**
 * Generate a new API key. Returns the raw key (shown once) + metadata.
 */
export async function generateApiKey(name: string): Promise<{ key: string; prefix: string; name: string }> {
  const raw = `sk-sent-${randomBytes(24).toString('hex')}`;
  const prefix = raw.slice(0, 16) + '...';
  const doc: ApiKeyDoc = {
    key_hash: hashKey(raw),
    prefix,
    name,
    created_at: new Date().toISOString(),
    last_used_at: null,
    requests: 0,
    active: true,
  };
  const db = getDb();
  await db.collection(COLLECTION).insertOne(doc);
  return { key: raw, prefix, name };
}

/**
 * Validate an API key. Returns true if valid + active.
 */
export async function validateApiKey(key: string): Promise<boolean> {
  if (!key) return false;
  const db = getDb();
  const hash = hashKey(key);
  const doc = await db.collection(COLLECTION).findOne({ key_hash: hash, active: true });
  if (!doc) return false;

  // Track usage (fire-and-forget)
  db.collection(COLLECTION).updateOne(
    { key_hash: hash },
    { $set: { last_used_at: new Date().toISOString() }, $inc: { requests: 1 } },
  ).catch(() => {});

  return true;
}

/**
 * List all keys (without hashes, only prefixes).
 */
export async function listApiKeys(): Promise<Array<Omit<ApiKeyDoc, 'key_hash'>>> {
  const db = getDb();
  const docs = await db.collection(COLLECTION)
    .find({}, { projection: { _id: 0, key_hash: 0 } })
    .sort({ created_at: -1 })
    .toArray();
  return docs as any;
}

/**
 * Revoke a key by prefix.
 */
export async function revokeApiKey(prefix: string): Promise<boolean> {
  const db = getDb();
  const result = await db.collection(COLLECTION).updateOne(
    { prefix },
    { $set: { active: false } },
  );
  return result.modifiedCount > 0;
}

/**
 * Delete a key permanently by prefix.
 */
export async function deleteApiKey(prefix: string): Promise<boolean> {
  const db = getDb();
  const result = await db.collection(COLLECTION).deleteOne({ prefix });
  return result.deletedCount > 0;
}
