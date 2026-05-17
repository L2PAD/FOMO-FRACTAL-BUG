/**
 * Manual Cookie Import Script (DEV MODE)
 * 
 * Imports Twitter cookies from a JSON file and creates a source session
 * for Phase 3 testing.
 * 
 * Usage:
 * 1. Export cookies from browser to /app/backend/cookies.json
 * 2. Run: npx tsx scripts/import-twitter-cookies.ts
 * 
 * Cookie JSON format:
 * [
 *   { "name": "auth_token", "value": "...", "domain": ".twitter.com" },
 *   ...
 * ]
 */

import mongoose from 'mongoose';
import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import dotenv from 'dotenv';

dotenv.config();

// =====================================================
// Configuration
// =====================================================

const SOURCE_USER_ID = 'DEV_SOURCE_USER';
const COOKIES_FILE = path.join(process.cwd(), 'cookies.json');

// =====================================================
// Crypto (inline to avoid import issues)
// =====================================================

function encryptCookies(cookies: any[], keyHex: string): { enc: string; iv: string; tag: string } {
  const key = Buffer.from(keyHex, 'hex');
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);

  const plaintext = Buffer.from(JSON.stringify(cookies), 'utf8');
  const enc = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();

  return {
    enc: enc.toString('base64'),
    iv: iv.toString('base64'),
    tag: tag.toString('base64'),
  };
}

// =====================================================
// Main Import Logic
// =====================================================

async function importCookies(): Promise<void> {
  const mongoUrl = process.env.MONGO_URL || process.env.MONGODB_URI || 'mongodb://localhost:27017/ai_on_crypto';
  const encKey = process.env.COOKIE_ENC_KEY;

  if (!encKey) {
    throw new Error('COOKIE_ENC_KEY is required in .env');
  }

  // Check cookies file exists
  if (!fs.existsSync(COOKIES_FILE)) {
    console.log('❌ cookies.json not found!');
    console.log('');
    console.log('📋 HOW TO EXPORT COOKIES:');
    console.log('1. Open twitter.com in Chrome');
    console.log('2. Press F12 → Console');
    console.log('3. Paste this and press Enter:');
    console.log('');
    console.log(`copy(JSON.stringify(document.cookie.split('; ').map(c => {
  const [name, ...rest] = c.split('=');
  return { name, value: rest.join('='), domain: '.twitter.com', path: '/' };
}), null, 2))`);
    console.log('');
    console.log('4. Save to: /app/backend/cookies.json');
    process.exit(1);
  }

  // Load cookies
  const cookiesRaw = fs.readFileSync(COOKIES_FILE, 'utf8');
  let cookies: any[];
  
  try {
    cookies = JSON.parse(cookiesRaw);
  } catch (err) {
    throw new Error('Invalid JSON in cookies.json');
  }

  if (!Array.isArray(cookies) || cookies.length === 0) {
    throw new Error('cookies.json must be a non-empty array');
  }

  // Validate required cookies
  const requiredCookies = ['auth_token', 'ct0'];
  const cookieNames = cookies.map(c => c.name);
  const missing = requiredCookies.filter(r => !cookieNames.includes(r));
  
  if (missing.length > 0) {
    throw new Error(`Missing required cookies: ${missing.join(', ')}`);
  }

  console.log(`📄 Loaded ${cookies.length} cookies from file`);
  console.log(`   Found: ${cookieNames.slice(0, 5).join(', ')}${cookies.length > 5 ? '...' : ''}`);

  // Encrypt cookies
  const { enc, iv, tag } = encryptCookies(cookies, encKey);
  console.log('🔐 Cookies encrypted');

  // Connect to MongoDB
  console.log('🔌 Connecting to MongoDB...');
  await mongoose.connect(mongoUrl);
  console.log('✅ Connected');

  const db = mongoose.connection.db;
  const sessionsCol = db.collection('user_twitter_sessions');

  // Extract username from cookies if possible
  let username = 'dev_user';
  const twidCookie = cookies.find(c => c.name === 'twid');
  if (twidCookie) {
    // twid format: u%3D1234567890
    const match = twidCookie.value.match(/u%3D(\d+)/);
    if (match) {
      username = `user_${match[1]}`;
    }
  }

  // Delete existing DEV source sessions
  const deleted = await sessionsCol.deleteMany({ 
    ownerUserId: SOURCE_USER_ID,
    source: 'manual-import',
  });
  if (deleted.deletedCount > 0) {
    console.log(`🗑️  Deleted ${deleted.deletedCount} old DEV source session(s)`);
  }

  // Create new session
  const session = await sessionsCol.insertOne({
    ownerUserId: SOURCE_USER_ID,
    accountId: `dev_account_${Date.now()}`,
    username,
    cookiesEnc: enc,
    cookiesIv: iv,
    cookiesTag: tag,
    status: 'OK',
    isActive: true,
    isTest: true,
    source: 'manual-import',
    lastOkAt: new Date(),
    createdAt: new Date(),
  });

  console.log('');
  console.log('='.repeat(50));
  console.log('✅ COOKIES IMPORTED SUCCESSFULLY');
  console.log('='.repeat(50));
  console.log(`Session ID:  ${session.insertedId}`);
  console.log(`Username:    ${username}`);
  console.log(`Source User: ${SOURCE_USER_ID}`);
  console.log('');
  console.log('📋 NEXT STEPS:');
  console.log('1. Add to /app/backend/.env:');
  console.log(`   TEST_COOKIE_SOURCE_USER_ID=${SOURCE_USER_ID}`);
  console.log('');
  console.log('2. Run seeder:');
  console.log('   npx tsx scripts/seed-test-data.ts');
  console.log('');
  console.log('3. Run tests:');
  console.log('   npx tsx scripts/run-test-parsing.ts');
  console.log('='.repeat(50));

  await mongoose.disconnect();
}

// =====================================================
// Run
// =====================================================
importCookies()
  .then(() => process.exit(0))
  .catch(err => {
    console.error('❌ Import failed:', err.message);
    process.exit(1);
  });
