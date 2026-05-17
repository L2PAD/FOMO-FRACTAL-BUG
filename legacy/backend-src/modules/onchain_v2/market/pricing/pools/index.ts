/**
 * OnChain V2 — Pools Module Index
 * =================================
 * 
 * STEP 2: Pool Scoring & Auto-Activation
 */

// Constants
export { SCORING, DISCOVERY } from './poolScoring.constants';

// Services
export { poolScoringService, PoolScoringService } from './poolScoring.service';
export type { PoolStatus, ScoreBreakdown, PoolScoreResult } from './poolScoring.service';

export { poolDiscoveryService, PoolDiscoveryService } from './poolDiscovery.service';
export type { DiscoveryResult } from './poolDiscovery.service';

export { tokenCandidatesService, TokenCandidatesService } from './tokenCandidates.service';
export type { TokenCandidate } from './tokenCandidates.service';

export { poolFinderService, PoolFinderService } from './poolFinder.service';

export { bestPoolResolver } from './bestPool.resolver';
export type { BestPoolResult } from './bestPool.resolver';

// Job
export { 
  startPoolDiscoveryJob, 
  stopPoolDiscoveryJob,
  forceRunPoolDiscoveryJob,
  getPoolDiscoveryJobStatus,
} from './poolDiscovery.job';

// Routes
export { poolRoutes } from './pool.routes';

console.log('[OnChain V2] Pools Module loaded');
