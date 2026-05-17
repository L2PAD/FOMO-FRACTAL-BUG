/**
 * Test SessionSelector directly
 */
import mongoose from 'mongoose';
import { SessionSelectorService } from '../src/modules/twitter-user/services/session-selector.service.js';
import { CryptoService } from '../src/modules/twitter-user/crypto/crypto.service.js';

const MONGO_URL = 'mongodb://localhost:27017/test';
const TEST_USER_ID = 'dev-user';
const COOKIE_ENC_KEY = process.env.COOKIE_ENC_KEY || 'a36b23e52a3ff4a238edef9f777074e4ed3c28d79b9df34da283098f534476b5';

async function testSelector() {
  try {
    console.log('Connecting to MongoDB...');
    await mongoose.connect(MONGO_URL);

    const crypto = new CryptoService(COOKIE_ENC_KEY);
    const selector = new SessionSelectorService(crypto);

    console.log('\n[Test] Calling selectForUser...');
    const result = await selector.selectForUser(TEST_USER_ID, { mode: 'AUTO' });

    console.log('\n[Result]');
    console.log('- ok:', result.ok);
    console.log('- reason:', result.reason || 'N/A');
    
    if (result.ok && result.config) {
      console.log('- accountId:', result.meta?.chosenAccount?.username);
      console.log('- sessionId:', result.meta?.session?.sessionId?.slice(0, 8) + '...');
      console.log('- cookies count:', result.config.cookies?.length || 0);
      console.log('- scrollProfileHint:', result.config.scrollProfileHint);
    }

    await mongoose.disconnect();
    process.exit(result.ok ? 0 : 1);
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

testSelector();
