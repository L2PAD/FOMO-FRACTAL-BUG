/**
 * Test integration service logic directly
 */
import mongoose from 'mongoose';

const MONGO_URL = 'mongodb://localhost:27017/crypto_analytics';
const TEST_USER_ID = 'dev-user';

async function testIntegrationLogic() {
  try {
    console.log('Connecting to MongoDB...');
    await mongoose.connect(MONGO_URL);

    // Define models
    const TwitterConsentModel = mongoose.model('TwitterConsent',
      new mongoose.Schema({}, { strict: false }),
      'twitter_consents'
    );

    const UserTwitterAccountModel = mongoose.model('UserTwitterAccount',
      new mongoose.Schema({}, { strict: false }),
      'user_twitter_accounts'
    );

    const UserTwitterSessionModel = mongoose.model('UserTwitterSession',
      new mongoose.Schema({}, { strict: false }),
      'user_twitter_sessions'
    );

    // Replicate buildContext logic
    const scope = { ownerType: 'USER', ownerUserId: TEST_USER_ID };

    console.log('\n[Test] Building context for user:', TEST_USER_ID);
    console.log('[Test] Scope:', JSON.stringify(scope));

    const [consent, accountsCount, sessions] = await Promise.all([
      TwitterConsentModel.findOne({ ownerUserId: TEST_USER_ID }).lean(),
      UserTwitterAccountModel.countDocuments(scope),
      UserTwitterSessionModel.find(scope).select('status').lean(),
    ]);

    console.log('\n[Results]');
    console.log('- Consent:', consent ? { accepted: consent.accepted } : null);
    console.log('- Accounts count:', accountsCount);
    console.log('- Sessions:', sessions.length);
    console.log('- Sessions by status:', {
      OK: sessions.filter(s => s.status === 'OK').length,
      STALE: sessions.filter(s => s.status === 'STALE').length,
      INVALID: sessions.filter(s => s.status === 'INVALID').length,
    });

    const ctx = {
      hasConsent: !!consent?.accepted,
      accountsCount,
      sessionsCount: sessions.length,
      okSessionsCount: sessions.filter(s => s.status === 'OK').length,
      staleSessionsCount: sessions.filter(s => s.status === 'STALE').length,
      invalidSessionsCount: sessions.filter(s => s.status === 'INVALID').length,
    };

    console.log('\n[Context]', JSON.stringify(ctx, null, 2));

    // Expected state logic
    if (!ctx.hasConsent) {
      console.log('\n❌ State: NEED_CONSENT');
    } else if (ctx.accountsCount === 0) {
      console.log('\n❌ State: NEED_ACCOUNT');
    } else if (ctx.okSessionsCount === 0) {
      console.log('\n❌ State: NEED_COOKIES or SESSION_STALE');
    } else {
      console.log('\n✅ State: SESSION_OK');
    }

    await mongoose.disconnect();
    process.exit(0);
  } catch (error) {
    console.error('Error:', error);
    process.exit(1);
  }
}

testIntegrationLogic();
