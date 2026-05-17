/**
 * OnChain V2 — Governance Routes (Admin Only)
 * =============================================
 * 
 * REST API for governance management.
 * All routes require admin authentication.
 */

import { FastifyInstance, FastifyRequest, FastifyReply } from 'fastify';
import {
  OnchainGovWeights,
  OnchainGovThresholds,
  OnchainGovGuardrails,
  OnchainGovPolicyStatus,
} from './contracts.js';
import { governanceService } from './governance.service.js';

// ═══════════════════════════════════════════════════════════════
// REQUEST TYPES
// ═══════════════════════════════════════════════════════════════

interface ProposePolicyBody {
  name: string;
  description?: string;
  version: string;
  weights: OnchainGovWeights;
  thresholds: OnchainGovThresholds;
  guardrails: OnchainGovGuardrails;
}

interface DryRunBody {
  weights: OnchainGovWeights;
  thresholds: OnchainGovThresholds;
  guardrails: OnchainGovGuardrails;
}

interface ApplyPolicyBody {
  policyId: string;
}

// ═══════════════════════════════════════════════════════════════
// HANDLERS
// ═══════════════════════════════════════════════════════════════

async function getStateHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const state = await governanceService.getState();
    const activePolicy = await governanceService.getActivePolicy();
    const guardrailsEval = await governanceService.evaluateGuardrails();
    
    return {
      ok: true,
      state,
      activePolicy: activePolicy ? {
        id: activePolicy.id,
        version: activePolicy.version,
        name: activePolicy.name,
        status: activePolicy.status,
      } : null,
      guardrails: guardrailsEval,
      timestamp: Date.now(),
    };
  } catch (error) {
    console.error('[Governance] Get state error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function getActivePolicyHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const policy = await governanceService.getActivePolicy();
    
    if (!policy) {
      return {
        ok: false,
        error: 'No active policy',
      };
    }
    
    return {
      ok: true,
      policy,
    };
  } catch (error) {
    console.error('[Governance] Get active policy error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function listPoliciesHandler(
  request: FastifyRequest<{
    Querystring: { status?: OnchainGovPolicyStatus };
  }>,
  reply: FastifyReply
) {
  try {
    const policies = await governanceService.listPolicies(request.query.status);
    
    return {
      ok: true,
      policies,
      count: policies.length,
    };
  } catch (error) {
    console.error('[Governance] List policies error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function proposePolicyHandler(
  request: FastifyRequest<{ Body: ProposePolicyBody }>,
  reply: FastifyReply
) {
  try {
    const actor = (request.headers['x-actor'] as string) || 'ADMIN';
    const policy = await governanceService.proposePolicy(request.body, actor);
    
    return {
      ok: true,
      policy,
      message: `Policy ${policy.id} proposed successfully`,
    };
  } catch (error) {
    console.error('[Governance] Propose policy error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function dryRunHandler(
  request: FastifyRequest<{ Body: DryRunBody }>,
  reply: FastifyReply
) {
  try {
    const result = await governanceService.dryRun(request.body);
    
    return {
      ok: true,
      result,
    };
  } catch (error) {
    console.error('[Governance] Dry run error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function applyPolicyHandler(
  request: FastifyRequest<{ Body: ApplyPolicyBody }>,
  reply: FastifyReply
) {
  try {
    const actor = (request.headers['x-actor'] as string) || 'ADMIN';
    const state = await governanceService.applyPolicy(request.body.policyId, actor);
    
    return {
      ok: true,
      state,
      message: `Policy ${request.body.policyId} applied successfully`,
    };
  } catch (error) {
    console.error('[Governance] Apply policy error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function getAuditLogHandler(
  request: FastifyRequest<{
    Querystring: { limit?: string; action?: string };
  }>,
  reply: FastifyReply
) {
  try {
    const limit = request.query.limit ? parseInt(request.query.limit) : 50;
    const entries = await governanceService.getAuditLog(limit, request.query.action);
    
    return {
      ok: true,
      entries,
      count: entries.length,
    };
  } catch (error) {
    console.error('[Governance] Get audit log error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

async function healthCheckHandler(
  request: FastifyRequest,
  reply: FastifyReply
) {
  try {
    const state = await governanceService.updateHealthStatus();
    const decision = await governanceService.makeDecision();
    
    return {
      ok: true,
      state,
      decision,
    };
  } catch (error) {
    console.error('[Governance] Health check error:', error);
    return {
      ok: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// ROUTE REGISTRATION
// ═══════════════════════════════════════════════════════════════

export async function onchainV2GovernanceRoutes(fastify: FastifyInstance): Promise<void> {
  // State & Health
  fastify.get('/state', getStateHandler);
  fastify.get('/health-check', healthCheckHandler);
  
  // Policy CRUD
  fastify.get('/policy/active', getActivePolicyHandler);
  fastify.get('/policies', listPoliciesHandler);
  fastify.post('/policy/propose', proposePolicyHandler);
  fastify.post('/policy/dry-run', dryRunHandler);
  fastify.post('/policy/apply', applyPolicyHandler);
  
  // Audit
  fastify.get('/audit', getAuditLogHandler);
  
  console.log('[OnChain V2] Governance routes registered');
}

console.log('[OnChain V2] Governance Routes module loaded');
