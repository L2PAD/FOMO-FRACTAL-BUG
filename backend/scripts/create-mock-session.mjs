/**
 * Create Mock Twitter Session for E2E Testing
 * 
 * Creates:
 * 1. Consent record
 * 2. Twitter Account
 * 3. Twitter Session with mock cookies
 */

import mongoose from 'mongoose';
import crypto from 'crypto';

// Connect to MongoDB
const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017/test';

// Mock user ID for testing (matches dev fallback in require-user.hook.ts)
const TEST_USER_ID = 'dev-user';

// Encryption (same key as in backend .env)
const COOKIE_ENC_KEY = process.env.COOKIE_ENC_KEY || 'a36b23e52a3ff4a238edef9f777074e4ed3c28d79b9df34da283098f534476b5';

function encryptCookies(cookieData) {
  const algorithm = 'aes-256-gcm';
  const key = Buffer.from(COOKIE_ENC_KEY, 'hex');
  const iv = crypto.randomBytes(12); // GCM uses 12 bytes IV
  
  const cipher = crypto.createCipheriv(algorithm, key, iv);
  let encrypted = cipher.update(JSON.stringify(cookieData), 'utf8');
  encrypted = Buffer.concat([encrypted, cipher.final()]);
  const authTag = cipher.getAuthTag();
  
  return {
    cookiesEnc: encrypted.toString('base64'),
    cookiesIv: iv.toString('base64'),
    cookiesTag: authTag.toString('base64'),
  };
}

async function createMockSession() {
  try {
    console.log('[Setup] Connecting to MongoDB...');
    await mongoose.connect(MONGO_URL);
    console.log('[Setup] Connected');

    // 1. Create Consent
    console.log('\n[1/3] Creating consent record...');
    const ConsentModel = mongoose.model('TwitterConsent', new mongoose.Schema({
      ownerUserId: String,
      accepted: Boolean,
      acceptedAt: Date,
      ip: String,
      userAgent: String,
      version: String,
    }), 'twitter_consents');

    await ConsentModel.findOneAndUpdate(
      { ownerUserId: TEST_USER_ID },
      {
        ownerUserId: TEST_USER_ID,
        accepted: true,
        acceptedAt: new Date(),
        ip: '127.0.0.1',
        userAgent: 'Mock Test Agent',
        version: 'v1',
      },
      { upsert: true, new: true }
    );
    console.log('✅ Consent created');

    // 2. Create Account
    console.log('\n[2/3] Creating Twitter account...');
    const AccountModel = mongoose.model('UserTwitterAccount', new mongoose.Schema({
      ownerUserId: String,
      ownerType: String,
      provider: String,
      providerUserId: String,
      username: String,
      displayName: String,
      status: String,
      enabled: Boolean,
      isPreferred: Boolean,
      createdAt: Date,
      updatedAt: Date,
    }), 'user_twitter_accounts');

    await AccountModel.updateOne(
      { ownerUserId: TEST_USER_ID, username: 'mock_test_user' },
      {
        $set: {
          ownerUserId: TEST_USER_ID,
          ownerType: 'USER',
          provider: 'twitter',
          providerUserId: 'mock_provider_001',
          username: 'mock_test_user',
          displayName: 'Mock Test Account',
          status: 'ACTIVE',
          enabled: true,
          isPreferred: false,
          updatedAt: new Date(),
        },
        $setOnInsert: {
          createdAt: new Date(),
        }
      },
      { upsert: true }
    );

    const account = await AccountModel.findOne({ ownerUserId: TEST_USER_ID, username: 'mock_test_user' });
    console.log('✅ Account created:', account._id);

    // 3. Create Session with mock cookies
    console.log('\n[3/3] Creating Twitter session with mock cookies...');
    const SessionModel = mongoose.model('UserTwitterSession', new mongoose.Schema({
      ownerUserId: String,
      ownerType: String,
      accountId: mongoose.Schema.Types.ObjectId,
      version: Number,
      status: String,
      isActive: Boolean,
      cookiesEnc: String,
      cookiesIv: String,
      cookiesTag: String,
      userAgent: String,
      proxyUrl: String,
      lastSyncAt: Date,
      lastUsedAt: Date,
      riskScore: Number,
      healthMetrics: Object,
      createdAt: Date,
      updatedAt: Date,
    }), 'user_twitter_sessions');

    // Mock cookies (structure valid, content fake)
    const mockCookies = [
      {
        name: 'auth_token',
        value: 'mock_auth_token_' + Date.now(),
        domain: '.twitter.com',
        path: '/',
        secure: true,
        httpOnly: true,
        sameSite: 'None'
      },
      {
        name: 'ct0',
        value: 'mock_ct0_' + Date.now(),
        domain: '.twitter.com',
        path: '/',
        secure: true,
        httpOnly: false,
        sameSite: 'Lax'
      },
      {
        name: 'guest_id',
        value: 'mock_guest_' + Date.now(),
        domain: '.twitter.com',
        path: '/',
        secure: false,
        httpOnly: false,
        sameSite: 'None'
      }
    ];

    // Wrap in object with 'cookies' field as expected by SessionSelector
    const encryptedCookies = encryptCookies({ cookies: mockCookies });

    const session = await SessionModel.create({
      ownerUserId: TEST_USER_ID,
      ownerType: 'USER',
      accountId: account._id,
      version: 1,
      status: 'OK',
      isActive: true,
      cookiesEnc: encryptedCookies.cookiesEnc,
      cookiesIv: encryptedCookies.cookiesIv,
      cookiesTag: encryptedCookies.cookiesTag,
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      proxyUrl: null,
      lastSyncAt: new Date(),
      lastUsedAt: null,
      riskScore: 10,
      healthMetrics: {
        avgLatency: 0,
        errorRate: 0,
        successRate: 100
      },
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    console.log('✅ Session created:', session._id);

    console.log('\n✅ MOCK SESSION SETUP COMPLETE');
    console.log('\nTest User ID:', TEST_USER_ID);
    console.log('Account ID:', account._id);
    console.log('Session ID:', session._id);
    console.log('\nYou can now test with this user ID.');

    await mongoose.disconnect();
    process.exit(0);

  } catch (error) {
    console.error('❌ Error:', error);
    process.exit(1);
  }
}

createMockSession();
