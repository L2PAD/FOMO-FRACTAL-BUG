/**
 * Phase 3.1 — Test Runner
 * 
 * Executes parsing tests against test users and targets.
 * Validates results automatically without manual checking.
 * 
 * Usage: npx ts-node scripts/run-test-parsing.ts
 * 
 * Prerequisites:
 * - seed-test-data.ts must be run first
 * - Real cookies must be available
 */

import mongoose from 'mongoose';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';

dotenv.config();

// =====================================================
// Types
// =====================================================

interface TestCase {
  userId: string;
  userEmail: string;
  targetId: string;
  targetType: string;
  targetValue: string;
  targetQuery: string;
}

interface TestResult {
  testCase: TestCase;
  status: 'PASS' | 'FAIL' | 'SKIP';
  taskId?: string;
  taskStatus?: string;
  fetched?: number;
  savedTweets?: number;
  statsUpdated?: boolean;
  durationMs?: number;
  error?: string;
  assertions: {
    name: string;
    passed: boolean;
    expected?: any;
    actual?: any;
  }[];
}

interface TestReport {
  phase: string;
  startedAt: string;
  finishedAt: string;
  totalTests: number;
  passed: number;
  failed: number;
  skipped: number;
  successRate: string;
  results: TestResult[];
  summary: {
    totalFetched: number;
    totalSaved: number;
    avgDurationMs: number;
    failedReasons: string[];
  };
}

// =====================================================
// Test Runner
// =====================================================

async function runTests(): Promise<TestReport> {
  // Use MONGODB_URI which contains the database name
  const mongoUrl = process.env.MONGODB_URI || process.env.MONGO_URL || 'mongodb://localhost:27017/ai_on_crypto';
  const apiBaseUrl = process.env.API_BASE_URL || 'http://localhost:8001';
  
  console.log('🔌 Connecting to MongoDB...');
  console.log('  URL:', mongoUrl);
  await mongoose.connect(mongoUrl);
  console.log('✅ Connected to database:', mongoose.connection.db?.databaseName);

  const db = mongoose.connection.db;
  
  // Collections
  const usersCol = db.collection('test_users');
  const sessionsCol = db.collection('user_twitter_sessions');
  const targetsCol = db.collection('user_twitter_parse_targets');
  const tweetsCol = db.collection('user_twitter_parsed_tweets');
  const tasksCol = db.collection('twitter_tasks');

  const report: TestReport = {
    phase: '3.1',
    startedAt: new Date().toISOString(),
    finishedAt: '',
    totalTests: 0,
    passed: 0,
    failed: 0,
    skipped: 0,
    successRate: '0%',
    results: [],
    summary: {
      totalFetched: 0,
      totalSaved: 0,
      avgDurationMs: 0,
      failedReasons: [],
    },
  };

  // =====================================================
  // Step 1: Gather Test Cases
  // =====================================================
  console.log('\n📋 Gathering test cases...');
  
  const testUsers = await usersCol.find({ isTest: true }).toArray();
  if (testUsers.length === 0) {
    console.log('❌ No test users found! Run seed-test-data.ts first.');
    await mongoose.disconnect();
    return report;
  }

  const testCases: TestCase[] = [];
  
  for (const user of testUsers) {
    const userId = user._id.toString();
    
    // Check if user has valid session
    const session = await sessionsCol.findOne({
      ownerUserId: userId,
      isTest: true,
      cookiesEnc: { $exists: true, $ne: null },
    });
    
    if (!session) {
      console.log(`  ⚠️  Skipping ${user.email} - no valid session`);
      continue;
    }

    // Get targets for this user
    const targets = await targetsCol.find({
      ownerUserId: userId,
      isTest: true,
      enabled: true,
    }).toArray();

    for (const target of targets) {
      testCases.push({
        userId,
        userEmail: user.email,
        targetId: target._id.toString(),
        targetType: target.type,
        targetValue: target.value,
        targetQuery: target.query,
      });
    }
  }

  console.log(`  ✅ Found ${testCases.length} test cases`);
  report.totalTests = testCases.length;

  if (testCases.length === 0) {
    console.log('❌ No test cases available. Check:');
    console.log('   1. Test users have sessions with cookies');
    console.log('   2. Test users have enabled targets');
    await mongoose.disconnect();
    return report;
  }

  // =====================================================
  // Step 2: Execute Tests
  // =====================================================
  console.log('\n🚀 Running tests...\n');

  // Only run first 5 tests in this iteration (avoid rate limits)
  const testsToRun = testCases.slice(0, 5);
  const durations: number[] = [];

  for (let i = 0; i < testsToRun.length; i++) {
    const tc = testsToRun[i];
    console.log(`[${i + 1}/${testsToRun.length}] Testing: ${tc.targetType} "${tc.targetValue}" for ${tc.userEmail}`);
    
    const result: TestResult = {
      testCase: tc,
      status: 'FAIL',
      assertions: [],
    };

    const startTime = Date.now();

    try {
      // Record initial state
      const initialTarget = await targetsCol.findOne({ _id: new mongoose.Types.ObjectId(tc.targetId) });
      const initialTweetCount = await tweetsCol.countDocuments({ ownerUserId: tc.userId });
      const initialRuns = initialTarget?.stats?.totalRuns || 0;

      // Create parsing task directly in MongoDB (simulating scheduler)
      const taskId = new mongoose.Types.ObjectId();
      const taskDoc = {
        _id: taskId,
        type: tc.targetType === 'KEYWORD' ? 'SEARCH' : 'ACCOUNT_TWEETS',
        status: 'PENDING',
        priority: 'NORMAL',
        priorityValue: 10,
        ownerType: 'USER',
        ownerUserId: tc.userId,
        scope: 'USER',  // CRITICAL: Required for worker to process as USER task
        payload: {
          targetId: tc.targetId,
          query: tc.targetQuery,
          keyword: tc.targetQuery,
          maxTweets: 20,
          limit: 20,
        },
        attempts: 0,
        maxAttempts: 3,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      await tasksCol.insertOne(taskDoc);
      result.taskId = taskId.toString();
      console.log(`  📝 Created task: ${taskId}`);

      // Wait for task to be processed (up to 60 seconds)
      let taskComplete = false;
      let finalTask: any = null;
      
      for (let wait = 0; wait < 60; wait++) {
        await new Promise(r => setTimeout(r, 1000));
        finalTask = await tasksCol.findOne({ _id: taskId });
        
        if (finalTask && ['OK', 'DONE', 'FAILED', 'BLOCKED', 'PARTIAL'].includes(finalTask.status)) {
          taskComplete = true;
          console.log(`  ✅ Task completed: ${finalTask.status}`);
          break;
        }
        
        if (wait % 10 === 0 && wait > 0) {
          console.log(`  ⏳ Waiting... (${wait}s, status: ${finalTask?.status || 'unknown'})`);
        }
      }

      result.durationMs = Date.now() - startTime;
      durations.push(result.durationMs);

      if (!taskComplete) {
        result.error = 'Task did not complete within 60 seconds';
        result.taskStatus = finalTask?.status || 'UNKNOWN';
        result.assertions.push({
          name: 'task_completed',
          passed: false,
          expected: 'OK|DONE|PARTIAL',
          actual: finalTask?.status,
        });
        report.failed++;
        report.summary.failedReasons.push(`Timeout: ${tc.targetValue}`);
        result.status = 'FAIL';
        report.results.push(result);
        continue;
      }

      result.taskStatus = finalTask.status;

      // =====================================================
      // Assertions
      // =====================================================

      // 1. Task status should be OK or PARTIAL
      const validStatuses = ['OK', 'DONE', 'PARTIAL'];
      const statusOk = validStatuses.includes(finalTask.status);
      result.assertions.push({
        name: 'task_status_ok',
        passed: statusOk,
        expected: validStatuses.join('|'),
        actual: finalTask.status,
      });

      // 2. Fetched count > 0 (unless legitimate empty)
      const fetched = finalTask.result?.fetched || finalTask.result?.length || 0;
      result.fetched = fetched;
      report.summary.totalFetched += fetched;
      
      // Allow 0 for empty searches, but flag it
      const fetchOk = fetched > 0 || finalTask.status === 'PARTIAL';
      result.assertions.push({
        name: 'fetched_tweets',
        passed: fetchOk,
        expected: '> 0',
        actual: fetched,
      });

      // 3. Tweets saved to database
      const finalTweetCount = await tweetsCol.countDocuments({ ownerUserId: tc.userId });
      const newTweets = finalTweetCount - initialTweetCount;
      result.savedTweets = newTweets;
      report.summary.totalSaved += newTweets;
      
      // Should have saved something if fetched > 0
      const saveOk = fetched === 0 || newTweets > 0;
      result.assertions.push({
        name: 'tweets_saved',
        passed: saveOk,
        expected: fetched > 0 ? '> 0' : '>= 0',
        actual: newTweets,
      });

      // 4. Target stats updated
      const finalTarget = await targetsCol.findOne({ _id: new mongoose.Types.ObjectId(tc.targetId) });
      const finalRuns = finalTarget?.stats?.totalRuns || 0;
      const statsUpdated = finalRuns > initialRuns;
      result.statsUpdated = statsUpdated;
      
      result.assertions.push({
        name: 'target_stats_updated',
        passed: statsUpdated,
        expected: `totalRuns > ${initialRuns}`,
        actual: finalRuns,
      });

      // 5. No duplicate tweets (spot check)
      const duplicates = await tweetsCol.aggregate([
        { $match: { ownerUserId: tc.userId } },
        { $group: { _id: '$tweetId', count: { $sum: 1 } } },
        { $match: { count: { $gt: 1 } } },
      ]).toArray();
      
      const noDupes = duplicates.length === 0;
      result.assertions.push({
        name: 'no_duplicates',
        passed: noDupes,
        expected: 0,
        actual: duplicates.length,
      });

      // Determine overall result
      const allPassed = result.assertions.every(a => a.passed);
      result.status = allPassed ? 'PASS' : 'FAIL';

      if (allPassed) {
        report.passed++;
        console.log(`  ✅ PASS (fetched: ${fetched}, saved: ${newTweets}, stats: ${statsUpdated ? 'updated' : 'not updated'})`);
      } else {
        report.failed++;
        const failedAssertions = result.assertions.filter(a => !a.passed).map(a => a.name);
        console.log(`  ❌ FAIL: ${failedAssertions.join(', ')}`);
        report.summary.failedReasons.push(`${tc.targetValue}: ${failedAssertions.join(', ')}`);
      }

    } catch (err: any) {
      result.error = err.message;
      result.status = 'FAIL';
      report.failed++;
      report.summary.failedReasons.push(`Error: ${tc.targetValue} - ${err.message}`);
      console.log(`  ❌ ERROR: ${err.message}`);
    }

    report.results.push(result);
    
    // Small delay between tests to avoid rate limits
    await new Promise(r => setTimeout(r, 2000));
  }

  // =====================================================
  // Finalize Report
  // =====================================================
  report.finishedAt = new Date().toISOString();
  report.successRate = report.totalTests > 0 
    ? `${Math.round((report.passed / testsToRun.length) * 100)}%`
    : '0%';
  report.summary.avgDurationMs = durations.length > 0
    ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
    : 0;

  // Save report
  const reportDir = '/app/test_reports';
  if (!fs.existsSync(reportDir)) {
    fs.mkdirSync(reportDir, { recursive: true });
  }
  
  const reportPath = path.join(reportDir, 'phase_3_1.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

  // =====================================================
  // Print Summary
  // =====================================================
  console.log('\n' + '='.repeat(60));
  console.log('📊 TEST REPORT — PHASE 3.1');
  console.log('='.repeat(60));
  console.log(`Total Tests:    ${testsToRun.length}`);
  console.log(`Passed:         ${report.passed} ✅`);
  console.log(`Failed:         ${report.failed} ❌`);
  console.log(`Skipped:        ${report.skipped} ⏭️`);
  console.log(`Success Rate:   ${report.successRate}`);
  console.log('---');
  console.log(`Total Fetched:  ${report.summary.totalFetched}`);
  console.log(`Total Saved:    ${report.summary.totalSaved}`);
  console.log(`Avg Duration:   ${report.summary.avgDurationMs}ms`);
  console.log('='.repeat(60));
  
  if (report.summary.failedReasons.length > 0) {
    console.log('\n❌ Failed Reasons:');
    report.summary.failedReasons.forEach(r => console.log(`  • ${r}`));
  }

  console.log(`\n📄 Report saved: ${reportPath}`);

  await mongoose.disconnect();
  return report;
}

// =====================================================
// Run
// =====================================================
runTests()
  .then(report => {
    const exitCode = report.failed > 0 ? 1 : 0;
    process.exit(exitCode);
  })
  .catch(err => {
    console.error('❌ Test runner failed:', err.message);
    process.exit(1);
  });
