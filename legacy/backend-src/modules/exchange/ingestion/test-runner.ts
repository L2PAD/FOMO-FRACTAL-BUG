/**
 * Quick Test Runner for Market Ingestion
 * Run: npx tsx src/modules/exchange/ingestion/test-runner.ts
 */
import { MarketIngestionService } from './services/market-ingestion.service.js';

const service = new MarketIngestionService();

async function testIngestion() {
  console.log('='.repeat(70));
  console.log('       TESTING MARKET INGESTION - PRODUCTION SYSTEM');
  console.log('='.repeat(70));

  const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];

  for (const symbol of SYMBOLS) {
    try {
      const result = await service.collect(symbol);

      if (result) {
        // Success analysis
        const perpProviders = result.providersUsed.filter((p) =>
          ['HYPERLIQUID', 'BYBIT_USDTPERP', 'BINANCE_USDM'].includes(p)
        );

        console.log(`\n${'='.repeat(70)}`);
        console.log(`✅ SUCCESS: ${symbol}`);
        console.log(`${'='.repeat(70)}`);
        console.log(`Price: $${result.price.toFixed(2)}`);
        console.log(`Quality: ${result.quality}`);
        console.log(`Providers (${result.providersUsed.length}): ${result.providersUsed.join(', ')}`);
        console.log(`Perp providers: ${perpProviders.length}`);
        console.log(`Spread: ${result.priceSpreadBps} bps`);
        if (result.fundingRate !== null) {
          console.log(`Funding Rate: ${(result.fundingRate * 100).toFixed(4)}%`);
        }
        if (result.openInterest !== null) {
          console.log(`Open Interest: ${result.openInterest.toLocaleString()}`);
        }
        console.log(`${'='.repeat(70)}`);
      } else {
        console.log(`\n❌ FAILED: ${symbol} - No data returned`);
      }
    } catch (error: any) {
      console.error(`\n💥 ERROR: ${symbol}`, error.message);
    }

    // Jitter between requests
    await new Promise((resolve) =>
      setTimeout(resolve, 500 + Math.random() * 1000)
    );
  }

  console.log(`\n${'='.repeat(70)}`);
  console.log('       TEST COMPLETED');
  console.log('='.repeat(70));
}

testIngestion().catch(console.error);
