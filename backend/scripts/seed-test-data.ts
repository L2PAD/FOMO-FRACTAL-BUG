/**
 * Phase 3.1 — Test Data Seeder
 * 
 * Creates reproducible test environment:
 * - Test users with isTest: true
 * - Twitter sessions (using real cookies)
 * - Parse targets (keywords + accounts)
 * 
 * Usage: npx ts-node scripts/seed-test-data.ts
 * 
 * Idempotent: safe to run multiple times
 */

import mongoose from 'mongoose';
import crypto from 'crypto';
import dotenv from 'dotenv';

dotenv.config();

// =====================================================
// Configuration
// =====================================================

const TEST_USERS = [
  { email: 'test+1@fomo.local', name: 'Test User 1' },
  { email: 'test+2@fomo.local', name: 'Test User 2' },
  { email: 'test+3@fomo.local', name: 'Test User 3' },
];

const TEST_TARGETS = [
  // Keywords
  { type: 'KEYWORD', value: 'bitcoin', query: 'bitcoin' },
  { type: 'KEYWORD', value: 'ethereum', query: 'ethereum' },
  { type: 'KEYWORD', value: 'crypto', query: 'crypto' },
  // Accounts
  { type: 'ACCOUNT', value: '@elonmusk', query: 'from:elonmusk' },
  { type: 'ACCOUNT', value: '@VitalikButerin', query: 'from:VitalikButerin' },
];

// =====================================================
// Schema Definitions (inline for script isolation)
// =====================================================

const TestUserSchema = new mongoose.Schema({
  email: { type: String, required: true, unique: true },
  name: { type: String },
  isTest: { type: Boolean, default: true },
  createdAt: { type: Date, default: Date.now },
});

const TestTwitterSessionSchema = new mongoose.Schema({
  ownerUserId: { type: String, required: true },
  accountId: { type: String, required: true },
  username: { type: String, required: true },
  cookiesEnc: { type: String }, // Encrypted cookies
  status: { type: String, enum: ['OK', 'STALE', 'BLOCKED'], default: 'OK' },
  isActive: { type: Boolean, default: true },
  isTest: { type: Boolean, default: true },
  lastOkAt: { type: Date },
  createdAt: { type: Date, default: Date.now },
});

const TestParseTargetSchema = new mongoose.Schema({
  ownerUserId: { type: String, required: true },
  type: { type: String, enum: ['KEYWORD', 'ACCOUNT'], required: true },
  value: { type: String, required: true },
  query: { type: String, required: true },
  enabled: { type: Boolean, default: true },
  isTest: { type: Boolean, default: true },
  stats: {
    totalRuns: { type: Number, default: 0 },
    totalPostsFetched: { type: Number, default: 0 },
    lastRunAt: { type: Date },
    lastError: { type: String },
  },
  createdAt: { type: Date, default: Date.now },
});

// =====================================================
// Main Seeder Logic
// =====================================================

interface SeedResult {
  users: { created: number; existing: number };
  sessions: { created: number; existing: number };
  targets: { created: number; existing: number };
  realCookiesFound: boolean;
}

async function seedTestData(): Promise<SeedResult> {
  // Use MONGODB_URI which contains the database name
  const mongoUrl = process.env.MONGODB_URI || process.env.MONGO_URL || 'mongodb://localhost:27017/ai_on_crypto';
  
  console.log('🔌 Connecting to MongoDB...');
  console.log('  URL:', mongoUrl);
  await mongoose.connect(mongoUrl);
  console.log('✅ Connected to database:', mongoose.connection.db?.databaseName);

  const db = mongoose.connection.db;
  
  // Collections
  const usersCol = db.collection('test_users');
  const sessionsCol = db.collection('user_twitter_sessions');
  const targetsCol = db.collection('user_twitter_parse_targets');
  
  const result: SeedResult = {
    users: { created: 0, existing: 0 },
    sessions: { created: 0, existing: 0 },
    targets: { created: 0, existing: 0 },
    realCookiesFound: false,
  };

  // =====================================================
  // Step 1: Create Test Users
  // =====================================================
  console.log('\n📦 Seeding test users...');
  
  for (const userData of TEST_USERS) {
    const existing = await usersCol.findOne({ email: userData.email });
    if (existing) {
      console.log(`  ⏭️  User ${userData.email} already exists`);
      result.users.existing++;
    } else {
      const userId = new mongoose.Types.ObjectId().toString();
      await usersCol.insertOne({
        _id: new mongoose.Types.ObjectId(userId),
        ...userData,
        isTest: true,
        createdAt: new Date(),
      });
      console.log(`  ✅ Created user ${userData.email} (${userId})`);
      result.users.created++;
    }
  }

  // =====================================================
  // Step 2: Find Real Cookies to Copy
  // =====================================================
  console.log('\n🔍 Looking for source cookies...');
  
  // First check if TEST_COOKIE_SOURCE_USER_ID is set
  const sourceUserId = process.env.TEST_COOKIE_SOURCE_USER_ID;
  
  let realSession: any = null;
  
  if (sourceUserId) {
    console.log(`  📌 Using TEST_COOKIE_SOURCE_USER_ID: ${sourceUserId}`);
    realSession = await sessionsCol.findOne({
      ownerUserId: sourceUserId,
      cookiesEnc: { $exists: true, $ne: null },
    });
    
    if (realSession) {
      console.log(`  ✅ Found source session: @${realSession.username}`);
      result.realCookiesFound = true;
    } else {
      console.log(`  ❌ No session found for source user ${sourceUserId}`);
    }
  }
  
  // Fallback: look for ANY session with cookies
  if (!realSession) {
    realSession = await sessionsCol.findOne({
      cookiesEnc: { $exists: true, $ne: null },
      $or: [
        { status: 'OK' },
        { isActive: true },
      ],
    });

    if (realSession) {
      console.log(`  ✅ Found session with cookies: @${realSession.username} (userId: ${realSession.ownerUserId})`);
      result.realCookiesFound = true;
    }
  }
  
  if (!realSession) {
    console.log('  ⚠️  No session with cookies found');
    console.log('');
    console.log('  👉 To import cookies manually:');
    console.log('     npx tsx scripts/import-twitter-cookies.ts');
    console.log('');
    console.log('  👉 Then add to .env:');
    console.log('     TEST_COOKIE_SOURCE_USER_ID=DEV_SOURCE_USER');
  }

  // =====================================================
  // Step 3: Create Test Sessions (copy real cookies) AND Accounts
  // =====================================================
  console.log('\n📦 Seeding test sessions and accounts...');
  
  const testUsers = await usersCol.find({ isTest: true }).toArray();
  const accountsCol = db.collection('user_twitter_accounts');
  
  for (const user of testUsers) {
    const userId = user._id.toString();
    const existing = await sessionsCol.findOne({ 
      ownerUserId: userId,
      isTest: true,
    });
    
    if (existing) {
      console.log(`  ⏭️  Session for ${user.email} already exists`);
      result.sessions.existing++;
    } else {
      const accountId = new mongoose.Types.ObjectId();
      const username = realSession?.username || `test_${user.email.split('@')[0].replace('+', '_')}`;
      
      // Create account first (required by SessionSelector)
      await accountsCol.insertOne({
        _id: accountId,
        ownerType: 'USER',
        ownerUserId: userId,
        username,
        displayName: user.name || username,
        enabled: true,
        isPreferred: true,
        priority: 10,
        requestsInWindow: 0,
        isTest: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      
      // Create session linked to account
      await sessionsCol.insertOne({
        ownerType: 'USER',
        ownerUserId: userId,
        accountId: accountId,
        version: 1,
        isActive: true,
        status: realSession ? 'OK' : 'STALE',
        riskScore: 10,
        lifetimeDaysEstimate: 14,
        lastOkAt: realSession ? new Date() : null,
        lastSyncAt: realSession ? new Date() : null,
        // Copy all encryption fields
        cookiesEnc: realSession?.cookiesEnc || null,
        cookiesIv: realSession?.cookiesIv || null,
        cookiesTag: realSession?.cookiesTag || null,
        userAgent: realSession?.userAgent || 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        consentAt: new Date(),
        isTest: true,
        createdAt: new Date(),
        updatedAt: new Date(),
      });
      console.log(`  ✅ Created account+session for ${user.email} (cookies: ${realSession ? 'copied' : 'empty'})`);
      result.sessions.created++;
    }
  }

  // =====================================================
  // Step 4: Create Test Targets
  // =====================================================
  console.log('\n📦 Seeding test targets...');
  
  for (const user of testUsers) {
    const userId = user._id.toString();
    
    for (const targetData of TEST_TARGETS) {
      const existing = await targetsCol.findOne({
        ownerUserId: userId,
        type: targetData.type,
        value: targetData.value,
        isTest: true,
      });
      
      if (existing) {
        result.targets.existing++;
      } else {
        await targetsCol.insertOne({
          ownerUserId: userId,
          type: targetData.type,
          value: targetData.value,
          query: targetData.query,
          enabled: true,
          isTest: true,
          stats: {
            totalRuns: 0,
            totalPostsFetched: 0,
            lastRunAt: null,
            lastError: null,
          },
          createdAt: new Date(),
        });
        result.targets.created++;
      }
    }
    console.log(`  ✅ Targets for ${user.email}: ${TEST_TARGETS.length} configured`);
  }

  // =====================================================
  // Summary
  // =====================================================
  console.log('\n' + '='.repeat(50));
  console.log('📊 SEED SUMMARY');
  console.log('='.repeat(50));
  console.log(`Users:    ${result.users.created} created, ${result.users.existing} existing`);
  console.log(`Sessions: ${result.sessions.created} created, ${result.sessions.existing} existing`);
  console.log(`Targets:  ${result.targets.created} created, ${result.targets.existing} existing`);
  console.log(`Real cookies: ${result.realCookiesFound ? '✅ Available' : '❌ Not found'}`);
  console.log('='.repeat(50));

  if (!result.realCookiesFound) {
    console.log('\n⚠️  WARNING: No real cookies found!');
    console.log('   Test sessions created but parsing will fail.');
    console.log('   Please sync a real Twitter account first via Chrome Extension.');
  }

  await mongoose.disconnect();
  console.log('\n✅ Seeding complete');
  
  return result;
}

// =====================================================
// Run
// =====================================================
seedTestData()
  .then(result => {
    console.log('\n📄 Result JSON:');
    console.log(JSON.stringify(result, null, 2));
    process.exit(0);
  })
  .catch(err => {
    console.error('❌ Seeding failed:', err.message);
    process.exit(1);
  });
