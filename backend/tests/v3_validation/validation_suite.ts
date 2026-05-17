/**
 * V3.1 VALIDATION TEST SUITE
 * 
 * Full E2E system validation for FREEZE v3.1
 */

const API_URL = process.env.REACT_APP_BACKEND_URL || 'https://expo-telegram-web.preview.emergentagent.com';

interface TestResult {
  test: string;
  passed: boolean;
  details: any;
  duration: number;
}

interface ValidationReport {
  timestamp: string;
  apiUrl: string;
  tests: TestResult[];
  summary: {
    total: number;
    passed: number;
    failed: number;
  };
}

async function fetchJson(url: string, options?: RequestInit) {
  const res = await fetch(url, { 
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers }
  });
  return res.json();
}

// ========== 1. E2E SYSTEM TESTS ==========

async function testSignalsEndpoint(network: string): Promise<TestResult> {
  const start = Date.now();
  try {
    const data = await fetchJson(`${API_URL}/api/v3/signals/market/${network}`);
    
    const checks = {
      ok: data.ok === true,
      hasDecision: ['BUY', 'SELL', 'NEUTRAL'].includes(data.data?.decision),
      hasQuality: ['HIGH', 'MEDIUM', 'LOW'].includes(data.data?.quality),
      hasDrivers: Object.keys(data.data?.drivers || {}).length === 6,
      hasGuardrails: data.data?.guardrails !== undefined,
      version: data.data?.version?.startsWith('v3'),
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: `signals_${network}`,
      passed: allPassed,
      details: { checks, response: { decision: data.data?.decision, quality: data.data?.quality, guardrails: data.data?.guardrails } },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: `signals_${network}`, passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

async function testStrategyEndpoint(network: string): Promise<TestResult> {
  const start = Date.now();
  try {
    const data = await fetchJson(`${API_URL}/api/v3/strategy/evaluate/${network}`);
    
    const checks = {
      ok: data.ok === true,
      hasPrimaryVerdict: data.data?.primaryVerdict !== undefined,
      hasStrategies: Array.isArray(data.data?.strategies) && data.data.strategies.length > 0,
      strategiesHaveVerdicts: data.data?.strategies?.every((s: any) => s.verdict !== undefined),
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: `strategy_evaluate_${network}`,
      passed: allPassed,
      details: { checks, primaryVerdict: data.data?.primaryVerdict, strategiesCount: data.data?.strategies?.length },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: `strategy_evaluate_${network}`, passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

async function testFullStrategyEndpoint(network: string): Promise<TestResult> {
  const start = Date.now();
  try {
    const data = await fetchJson(`${API_URL}/api/v3/strategy/full/${network}`);
    
    const checks = {
      ok: data.ok === true,
      hasSignalQuality: data.data?.signalQuality !== undefined,
      hasGuardrails: data.data?.guardrails !== undefined,
      hasStrategies: Array.isArray(data.data?.strategies),
      strategiesHaveBacktest: data.data?.strategies?.some((s: any) => s.backtest !== null),
      strategiesHaveFinalVerdict: data.data?.strategies?.every((s: any) => s.finalVerdict !== undefined),
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: `strategy_full_${network}`,
      passed: allPassed,
      details: { 
        checks, 
        signalQuality: data.data?.signalQuality,
        guardrailsBlocked: data.data?.guardrails?.blocked,
        strategySample: data.data?.strategies?.[0] 
      },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: `strategy_full_${network}`, passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

// ========== 2. GUARDRAILS TESTS ==========

async function testGuardrailsEnforcement(): Promise<TestResult> {
  const start = Date.now();
  try {
    // Get signals and check guardrails logic
    const signalsEth = await fetchJson(`${API_URL}/api/v3/signals/market/ethereum`);
    const signalsBnb = await fetchJson(`${API_URL}/api/v3/signals/market/bnb`);
    
    const checks = {
      ethGuardrailsPresent: signalsEth.data?.guardrails !== undefined,
      bnbGuardrailsPresent: signalsBnb.data?.guardrails !== undefined,
      // If quality is LOW, decision should be NEUTRAL (guardrail G1)
      ethLowQualityGuarded: signalsEth.data?.quality !== 'LOW' || signalsEth.data?.decision === 'NEUTRAL',
      bnbLowQualityGuarded: signalsBnb.data?.quality !== 'LOW' || signalsBnb.data?.decision === 'NEUTRAL',
      // If guardrails blocked, reasons should be present
      ethBlockedHasReasons: !signalsEth.data?.guardrails?.blocked || signalsEth.data?.guardrails?.blockedBy?.length > 0,
      bnbBlockedHasReasons: !signalsBnb.data?.guardrails?.blocked || signalsBnb.data?.guardrails?.blockedBy?.length > 0,
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'guardrails_enforcement',
      passed: allPassed,
      details: { 
        checks,
        eth: { quality: signalsEth.data?.quality, decision: signalsEth.data?.decision, guardrails: signalsEth.data?.guardrails },
        bnb: { quality: signalsBnb.data?.quality, decision: signalsBnb.data?.decision, guardrails: signalsBnb.data?.guardrails },
      },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'guardrails_enforcement', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

// ========== 3. STRATEGY CATALOG & VERDICT TESTS ==========

async function testStrategyCatalog(): Promise<TestResult> {
  const start = Date.now();
  try {
    const data = await fetchJson(`${API_URL}/api/v3/strategy/catalog`);
    
    const checks = {
      ok: data.ok === true,
      hasStrategies: data.data?.strategies?.length >= 5,
      strategiesHaveRequiredFields: data.data?.strategies?.every((s: any) => 
        s.id && s.name && s.networks && s.active !== undefined
      ),
      supportsEthereum: data.data?.strategies?.some((s: any) => s.networks?.includes('ethereum')),
      supportsBnb: data.data?.strategies?.some((s: any) => s.networks?.includes('bnb')),
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'strategy_catalog',
      passed: allPassed,
      details: { 
        checks,
        count: data.data?.count,
        strategies: data.data?.strategies?.map((s: any) => ({ id: s.id, name: s.name, networks: s.networks }))
      },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'strategy_catalog', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

async function testVerdictEndpoint(): Promise<TestResult> {
  const start = Date.now();
  try {
    const data = await fetchJson(`${API_URL}/api/v3/strategy/verdict`, {
      method: 'POST',
      body: JSON.stringify({
        strategyId: 'accumulation_play_v1',
        network: 'ethereum',
        backtestVerdict: 'GOOD',
        stabilityVerdict: 'STABLE',
        signalQuality: 'HIGH',
        guardrailBlocked: false
      })
    });
    
    const checks = {
      ok: data.ok === true,
      hasVerdict: ['PRODUCTION_READY', 'EXPERIMENT_ONLY', 'REJECTED', 'DISABLED'].includes(data.data?.verdict),
      hasReasons: Array.isArray(data.data?.reasons),
      hasUiConfig: data.data?.uiConfig !== undefined,
      productionReadyForGoodInputs: data.data?.verdict === 'PRODUCTION_READY',
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'verdict_endpoint',
      passed: allPassed,
      details: { checks, response: data.data },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'verdict_endpoint', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

async function testVerdictGuardrailBlock(): Promise<TestResult> {
  const start = Date.now();
  try {
    const data = await fetchJson(`${API_URL}/api/v3/strategy/verdict`, {
      method: 'POST',
      body: JSON.stringify({
        strategyId: 'accumulation_play_v1',
        network: 'ethereum',
        backtestVerdict: 'GOOD',
        signalQuality: 'LOW',
        guardrailBlocked: true,
        guardrailReasons: ['LOW_QUALITY', 'STALE_DATA']
      })
    });
    
    const checks = {
      ok: data.ok === true,
      verdictIsDisabled: data.data?.verdict === 'DISABLED',
      hasBlockReasons: data.data?.reasons?.length > 0,
      uiShowsNotToUser: data.data?.uiConfig?.showToUser === false,
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'verdict_guardrail_block',
      passed: allPassed,
      details: { checks, response: data.data },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'verdict_guardrail_block', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

// ========== 4. BACKTEST TESTS ==========

async function testBacktestEndpoint(): Promise<TestResult> {
  const start = Date.now();
  try {
    const data = await fetchJson(`${API_URL}/api/v3/strategy/backtest`, {
      method: 'POST',
      body: JSON.stringify({
        strategyId: 'accumulation_play_v1',
        network: 'ethereum',
        window: '14d'
      })
    });
    
    const checks = {
      ok: data.ok === true,
      hasMetrics: data.data?.metrics !== undefined,
      hasHitRate: typeof data.data?.metrics?.hitRate === 'number',
      hasMaxDrawdown: typeof data.data?.metrics?.maxDrawdown === 'number',
      hasVerdict: ['GOOD', 'MIXED', 'BAD', 'INSUFFICIENT_DATA'].includes(data.data?.verdict),
      hasReasons: Array.isArray(data.data?.reasons),
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'backtest_endpoint',
      passed: allPassed,
      details: { 
        checks, 
        metrics: data.data?.metrics,
        verdict: data.data?.verdict,
        reasons: data.data?.reasons
      },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'backtest_endpoint', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

// ========== 5. MULTICHAIN ISOLATION TEST ==========

async function testMultichainIsolation(): Promise<TestResult> {
  const start = Date.now();
  try {
    const [ethSignals, bnbSignals] = await Promise.all([
      fetchJson(`${API_URL}/api/v3/signals/market/ethereum`),
      fetchJson(`${API_URL}/api/v3/signals/market/bnb`)
    ]);
    
    const checks = {
      ethHasNetwork: ethSignals.data?.network === 'ethereum',
      bnbHasNetwork: bnbSignals.data?.network === 'bnb',
      // Both should have independent drivers
      ethHasOwnDrivers: ethSignals.data?.drivers !== undefined,
      bnbHasOwnDrivers: bnbSignals.data?.drivers !== undefined,
      // Timestamps should be similar (same request time) but not identical (different calculations)
      independentTimestamps: ethSignals.data?.timestamp !== bnbSignals.data?.timestamp,
      // Both should have guardrails evaluated independently
      ethGuardrails: ethSignals.data?.guardrails !== undefined,
      bnbGuardrails: bnbSignals.data?.guardrails !== undefined,
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'multichain_isolation',
      passed: allPassed,
      details: { 
        checks,
        eth: { network: ethSignals.data?.network, decision: ethSignals.data?.decision, quality: ethSignals.data?.quality },
        bnb: { network: bnbSignals.data?.network, decision: bnbSignals.data?.decision, quality: bnbSignals.data?.quality },
      },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'multichain_isolation', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

// ========== 6. ADMIN ENDPOINTS TEST ==========

async function testAdminEndpoints(): Promise<TestResult> {
  const start = Date.now();
  try {
    const [datasets, models, ablation] = await Promise.all([
      fetchJson(`${API_URL}/api/admin/ml/v3/dataset/list`),
      fetchJson(`${API_URL}/api/admin/ml/v3/models/shadow`),
      fetchJson(`${API_URL}/api/admin/ml/v3/ablation/history`)
    ]);
    
    const checks = {
      datasetsOk: datasets.ok === true,
      modelsOk: models.ok === true,
      ablationOk: ablation.ok === true,
      datasetsHaveData: datasets.data?.datasets?.length > 0,
      modelsHaveData: models.data?.models?.length > 0,
      ablationHasRows: ablation.data?.rows?.length > 0,
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'admin_endpoints',
      passed: allPassed,
      details: { 
        checks,
        datasetsCount: datasets.data?.datasets?.length,
        modelsCount: models.data?.models?.length,
        ablationCount: ablation.data?.rows?.length,
      },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'admin_endpoints', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

// ========== 7. HEALTH CHECK ==========

async function testHealthEndpoints(): Promise<TestResult> {
  const start = Date.now();
  try {
    const [signalsHealth, systemHealth] = await Promise.all([
      fetchJson(`${API_URL}/api/v3/signals/health`),
      fetchJson(`${API_URL}/api/system/health`)
    ]);
    
    const checks = {
      signalsHealthOk: signalsHealth.ok === true,
      systemHealthOk: systemHealth.status === 'ok' || systemHealth.ok === true,
      signalsOperational: signalsHealth.data?.status === 'operational',
    };

    const allPassed = Object.values(checks).every(v => v);
    
    return {
      test: 'health_endpoints',
      passed: allPassed,
      details: { checks, signalsHealth: signalsHealth.data, systemHealth },
      duration: Date.now() - start
    };
  } catch (err) {
    return { test: 'health_endpoints', passed: false, details: { error: (err as Error).message }, duration: Date.now() - start };
  }
}

// ========== MAIN RUNNER ==========

async function runValidation(): Promise<ValidationReport> {
  console.log('🧪 Starting V3.1 Validation Suite...\n');
  
  const tests: TestResult[] = [];
  
  // E2E System Tests
  console.log('1️⃣ E2E System Tests...');
  tests.push(await testSignalsEndpoint('ethereum'));
  tests.push(await testSignalsEndpoint('bnb'));
  tests.push(await testStrategyEndpoint('ethereum'));
  tests.push(await testStrategyEndpoint('bnb'));
  tests.push(await testFullStrategyEndpoint('ethereum'));
  
  // Guardrails Tests
  console.log('2️⃣ Guardrails Tests...');
  tests.push(await testGuardrailsEnforcement());
  
  // Strategy & Verdict Tests
  console.log('3️⃣ Strategy & Verdict Tests...');
  tests.push(await testStrategyCatalog());
  tests.push(await testVerdictEndpoint());
  tests.push(await testVerdictGuardrailBlock());
  
  // Backtest Tests
  console.log('4️⃣ Backtest Tests...');
  tests.push(await testBacktestEndpoint());
  
  // Multichain Tests
  console.log('5️⃣ Multichain Tests...');
  tests.push(await testMultichainIsolation());
  
  // Admin Tests
  console.log('6️⃣ Admin Endpoints Tests...');
  tests.push(await testAdminEndpoints());
  
  // Health Tests
  console.log('7️⃣ Health Endpoints Tests...');
  tests.push(await testHealthEndpoints());
  
  const passed = tests.filter(t => t.passed).length;
  const failed = tests.filter(t => !t.passed).length;
  
  const report: ValidationReport = {
    timestamp: new Date().toISOString(),
    apiUrl: API_URL,
    tests,
    summary: {
      total: tests.length,
      passed,
      failed
    }
  };
  
  console.log('\n========== VALIDATION REPORT ==========');
  console.log(`Total: ${report.summary.total} | ✅ Passed: ${passed} | ❌ Failed: ${failed}`);
  console.log('');
  
  for (const test of tests) {
    const icon = test.passed ? '✅' : '❌';
    console.log(`${icon} ${test.test} (${test.duration}ms)`);
    if (!test.passed) {
      console.log(`   Details: ${JSON.stringify(test.details, null, 2).slice(0, 200)}`);
    }
  }
  
  return report;
}

// Export for CLI usage
export { runValidation, ValidationReport, TestResult };
