/**
 * OnChain V2 — Stress Test Runner
 */

import mongoose from 'mongoose';

async function main() {
  // Connect to MongoDB
  const mongoUrl = process.env.MONGO_URL || 'mongodb://localhost:27017/cryptosignal';
  
  console.log('Connecting to MongoDB...');
  await mongoose.connect(mongoUrl);
  console.log('Connected.');
  
  // Import and run tests
  const { runAllTests } = await import('./stress_tests.js');
  
  const exitCode = await runAllTests();
  
  await mongoose.disconnect();
  console.log('\nMongoDB disconnected.');
  
  process.exit(exitCode);
}

main().catch(err => {
  console.error('Runner error:', err);
  process.exit(1);
});
