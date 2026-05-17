import crypto from 'crypto';
import mongoose from 'mongoose';

const MONGO_URL = 'mongodb://localhost:27017/test';
const COOKIE_ENC_KEY = 'a36b23e52a3ff4a238edef9f777074e4ed3c28d79b9df34da283098f534476b5';

async function testDecrypt() {
  await mongoose.connect(MONGO_URL);
  
  const session = await mongoose.connection.db.collection('user_twitter_sessions').findOne({ownerUserId: 'dev-user'});
  
  console.log('Session cookiesEnc length:', session.cookiesEnc?.length || 0);
  console.log('Session cookiesIv length:', session.cookiesIv?.length || 0);
  console.log('Session cookiesTag length:', session.cookiesTag?.length || 0);
  
  try {
    const key = Buffer.from(COOKIE_ENC_KEY, 'hex');
    const iv = Buffer.from(session.cookiesIv, 'base64');
    const tag = Buffer.from(session.cookiesTag, 'base64');
    const enc = Buffer.from(session.cookiesEnc, 'base64');
    
    const decipher = crypto.createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAuthTag(tag);
    
    const dec = Buffer.concat([decipher.update(enc), decipher.final()]);
    const cookies = JSON.parse(dec.toString('utf8'));
    
    console.log('\n✅ Decryption successful!');
    console.log('Cookies count:', cookies.length);
    console.log('Cookies:', JSON.stringify(cookies, null, 2));
  } catch (err) {
    console.error('❌ Decryption failed:', err.message);
  }
  
  await mongoose.disconnect();
  process.exit(0);
}

testDecrypt();
