/**
 * API Key Auth Middleware
 * 
 * USER LAYER AUTH (для extension и пользовательских запросов)
 * 
 * Порядок извлечения ключа:
 * 1. X-FOMO-API-KEY header
 * 2. Authorization: Bearer usr_xxx
 * 3. (legacy) body.apiKey - deprecated, будет удалено
 * 
 * Только usr_ ключи принимаются для USER endpoints
 */

import type { FastifyRequest, FastifyReply } from 'fastify';
import { ApiKeyService } from '../services/api-key.service.js';
import type { ApiKeyScope } from '../models/user-api-key.model.js';

const apiKeyService = new ApiKeyService();

/**
 * Extract USER API key from request (supports multiple sources)
 */
function extractUserApiKey(request: FastifyRequest): { key: string | null; source: string } {
  // 1. X-FOMO-API-KEY header (preferred)
  const fomoHeader = request.headers['x-fomo-api-key'];
  if (fomoHeader && typeof fomoHeader === 'string') {
    return { key: fomoHeader.trim(), source: 'x-fomo-api-key' };
  }
  
  // 2. Authorization: Bearer usr_xxx
  const authHeader = request.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const key = authHeader.slice(7).trim();
    return { key, source: 'authorization-bearer' };
  }
  
  // 3. Legacy: body.apiKey (deprecated - log warning)
  const body = request.body as any;
  if (body?.apiKey && typeof body.apiKey === 'string') {
    console.warn(`[UserAuth] DEPRECATED: apiKey in body from ${request.ip}. Use X-FOMO-API-KEY header.`);
    return { key: body.apiKey.trim(), source: 'body-legacy' };
  }
  
  return { key: null, source: 'none' };
}

/**
 * Middleware factory для проверки USER API key с определённым scope
 * 
 * Только usr_ ключи принимаются
 */
export function requireApiKey(scope: ApiKeyScope) {
  return async (request: FastifyRequest, reply: FastifyReply) => {
    const { key: apiKey, source } = extractUserApiKey(request);
    
    // 401: ключ отсутствует
    if (!apiKey) {
      return reply.code(401).send({
        ok: false,
        error: 'API key required. Use X-FOMO-API-KEY header.',
        code: 'AUTH_MISSING',
      });
    }
    
    // 403: ключ не usr_ (wrong type)
    if (!apiKey.startsWith('usr_')) {
      console.warn(`[UserAuth] Wrong key type: prefix=${apiKey.slice(0, 4)} source=${source}`);
      return reply.code(403).send({
        ok: false,
        error: 'Invalid key type. USER endpoints require usr_ keys.',
        code: 'AUTH_WRONG_TYPE',
      });
    }
    
    // Validate key
    const result = await apiKeyService.validate(apiKey, scope);
    
    if (!result.valid) {
      console.warn(`[UserAuth] Invalid key: source=${source} error=${result.error}`);
      return reply.code(401).send({
        ok: false,
        error: result.error || 'Invalid API key',
        code: 'AUTH_INVALID',
      });
    }
    
    console.log(`[UserAuth] OK: userId=${result.ownerUserId} source=${source} scope=${scope}`);
    
    // Attach ownerUserId to request
    (request as any).apiKeyUserId = result.ownerUserId;
    (request as any).apiKeySource = source;
  };
}

/**
 * Middleware for USER endpoints that accepts usr_ keys
 * Same as requireApiKey but explicit naming
 */
export const requireUserApiKey = requireApiKey;

/**
 * Get ownerUserId from API key auth
 */
export function getApiKeyUserId(request: FastifyRequest): string | undefined {
  return (request as any).apiKeyUserId;
}

/**
 * Require API key user ID (throws if not present)
 */
export function requireApiKeyUser(request: FastifyRequest): { id: string } {
  const userId = getApiKeyUserId(request);
  if (!userId) {
    throw new Error('API key authentication required');
  }
  return { id: userId };
}
