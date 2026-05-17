/**
 * Webhook Routes - Extension → Backend (Phase 1.1 + 1.2 + 2.2)
 * 
 * PHASE 2.2: Integrated with Twitter Error Code Registry
 * 
 * SECURITY:
 * - Extension НЕ передаёт userId в payload
 * - ownerUserId извлекается ТОЛЬКО из API key (Authorization header)
 * - accountId проверяется на ownership
 * 
 * PHASE 2.3: Added support for webhook API key in body (for Chrome Extension compatibility)
 */

import type { FastifyInstance } from 'fastify';
import { requireApiKey, requireApiKeyUser } from '../auth/api-key.middleware.js';
import type { CookieWebhookDTO } from '../dto/twitter-webhook.dto.js';
import type { SessionService } from '../services/session.service.js';

// Runtime imports
import { TwitterErrorCode, createErrorResponse } from '../../twitter/errors/index.js';

// Import session service for webhook API key validation
import { sessionService as adminSessionService } from '../../twitter/sessions/session.service.js';

export async function registerTwitterWebhookRoutes(
  app: FastifyInstance,
  deps: {
    sessions: SessionService;
  }
) {
  /**
   * POST /api/v4/twitter/sessions/webhook
   * 
   * Auth: DUAL MODE
   * - Mode 1: API Key в Authorization header (Bearer usr_xxx) with scope twitter:cookies:write
   * - Mode 2: Webhook API Key in body (apiKey field) - for Chrome Extension
   * 
   * Body: { accountId, cookies, userAgent?, ts?, qualityReport?, apiKey?, sessionId? }
   */
  app.post(
    '/api/v4/twitter/sessions/webhook',
    async (req, reply) => {
      try {
        const body = (req.body ?? {}) as CookieWebhookDTO & { 
          qualityReport?: any; 
          apiKey?: string;
          sessionId?: string;
          accountUsername?: string;
        };

        // MULTI-SOURCE AUTH MODE
        // Priority: X-FOMO-API-KEY header > Authorization Bearer > body.apiKey
        let isWebhookKeyAuth = false;
        let apiKey: string | null = null;
        
        // 1. Check X-FOMO-API-KEY header (preferred for extension)
        const fomoApiKeyHeader = req.headers['x-fomo-api-key'];
        if (fomoApiKeyHeader && typeof fomoApiKeyHeader === 'string') {
          apiKey = fomoApiKeyHeader.trim();
          console.log(`[Webhook] Auth via X-FOMO-API-KEY header`);
        }
        // 2. Check Authorization Bearer header
        else {
          const authHeader = req.headers.authorization;
          if (authHeader && authHeader.startsWith('Bearer ')) {
            apiKey = authHeader.slice(7).trim();
            console.log(`[Webhook] Auth via Authorization Bearer header`);
          }
        }
        // 3. Check body.apiKey (legacy Chrome Extension mode)
        if (!apiKey && body.apiKey) {
          apiKey = body.apiKey;
          console.log(`[Webhook] Auth via body.apiKey (legacy mode)`);
        }
        
        // No auth provided
        if (!apiKey) {
          return reply.code(401).send(createErrorResponse(
            TwitterErrorCode.SESSION_INVALID,
            { reason: 'Missing authentication. Provide usr_ key in X-FOMO-API-KEY header.' }
          ));
        }
        
        // Validate based on key type
        if (apiKey.startsWith('usr_')) {
          // USER API key - use requireApiKey middleware logic
          try {
            // Manual validation for usr_ keys
            const { ApiKeyService } = await import('../services/api-key.service.js');
            const apiKeyService = new ApiKeyService();
            const validation = await apiKeyService.validate(apiKey, 'twitter:cookies:write');
            if (!validation.valid) {
              return reply.code(401).send(createErrorResponse(
                TwitterErrorCode.SESSION_INVALID,
                { reason: validation.error || 'Invalid or expired API key' }
              ));
            }
            // Set user context
            (req as any).apiKeyUserId = validation.ownerUserId;
            console.log(`[Webhook] usr_ key validated for user: ${validation.ownerUserId}`);
          } catch (authErr: any) {
            return reply.code(401).send(createErrorResponse(
              TwitterErrorCode.SESSION_INVALID,
              { reason: 'Invalid Bearer token' }
            ));
          }
        } else {
          // Webhook API key (admin mode)
          if (!adminSessionService.validateApiKey(apiKey)) {
            return reply.code(401).send(createErrorResponse(
              TwitterErrorCode.SESSION_INVALID,
              { reason: 'Invalid webhook API key. Use usr_ key from /settings/api-keys.' }
            ));
          }
          isWebhookKeyAuth = true;
          console.log(`[Webhook] Auth via webhook API key (admin mode)`);
        }

        // For webhook key auth, use simplified flow (admin session service)
        if (isWebhookKeyAuth) {
          const sessionId = body.sessionId || body.accountUsername || `session_${Date.now()}`;
          
          if (!body.cookies || !Array.isArray(body.cookies) || body.cookies.length === 0) {
            return reply.code(400).send(createErrorResponse(
              TwitterErrorCode.COOKIES_EMPTY,
              { sessionId }
            ));
          }

          console.log(`[Webhook] Ingesting session: ${sessionId} (${body.cookies.length} cookies)`);

          // Use admin session service for simplified flow
          const session = await adminSessionService.ingestSession({
            sessionId,
            cookies: body.cookies,
            userAgent: body.userAgent,
            accountUsername: body.accountUsername,
            accountId: body.accountId,
          });

          return reply.send({
            ok: true,
            data: {
              stored: body.cookies.length,
              status: session.status,
              sessionId: session.sessionId,
              sessionVersion: session.version || 1,
            }
          });
        }

        // Original Bearer token flow
        const user = requireApiKeyUser(req);
        const dto = body as CookieWebhookDTO & { qualityReport?: any };

        // Validate payload - PHASE 2.2: Return structured errors
        if (!dto.accountId) {
          return reply.code(400).send(createErrorResponse(
            TwitterErrorCode.MISSING_PARAMETER,
            { parameter: 'accountId' }
          ));
        }

        if (!Array.isArray(dto.cookies) || dto.cookies.length === 0) {
          return reply.code(400).send(createErrorResponse(
            TwitterErrorCode.COOKIES_EMPTY,
            { accountId: dto.accountId }
          ));
        }

        // Log quality report if provided (Phase 2.1 integration)
        if (dto.qualityReport) {
          app.log.info({ 
            accountId: dto.accountId, 
            qualityStatus: dto.qualityReport.status,
            cookieCount: dto.qualityReport.cookieCount 
          }, 'Cookie quality report received');
        }

        // Ingest webhook (ownership check + session versioning inside)
        const result = await deps.sessions.ingestWebhook(user.id, dto);
        
        return reply.send({ 
          ok: true, 
          data: result 
        });
      } catch (err: any) {
        const dto = (req.body ?? {}) as CookieWebhookDTO;
        
        // PHASE 2.2: Known errors with structured responses
        if (err.message === 'CONSENT_REQUIRED') {
          return reply.code(403).send(createErrorResponse(
            TwitterErrorCode.POLICY_BLOCKED,
            { reason: 'consent_required', accountId: dto.accountId }
          ));
        }
        
        if (err.message === 'ACCOUNT_NOT_FOUND') {
          return reply.code(404).send(createErrorResponse(
            TwitterErrorCode.ACCOUNT_NOT_FOUND,
            { accountId: dto.accountId }
          ));
        }
        
        if (err.message === 'ACCOUNT_OWNERSHIP_VIOLATION') {
          return reply.code(403).send(createErrorResponse(
            TwitterErrorCode.POLICY_BLOCKED,
            { reason: 'ownership_violation', accountId: dto.accountId }
          ));
        }
        
        if (err.message === 'SESSION_INVALID' || err.message?.includes('session')) {
          return reply.code(412).send(createErrorResponse(
            TwitterErrorCode.SESSION_INVALID,
            { accountId: dto.accountId, originalError: err.message }
          ));
        }

        // Unknown error - still return structured format
        app.log.error(err, 'Webhook error');
        return reply.code(500).send(createErrorResponse(
          TwitterErrorCode.INTERNAL_ERROR,
          { accountId: dto.accountId, originalError: err.message }
        ));
      }
    }
  );
}
