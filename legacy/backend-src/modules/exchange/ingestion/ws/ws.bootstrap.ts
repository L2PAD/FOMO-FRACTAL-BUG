/**
 * WS Bootstrap - Запуск WebSocket clients на старте приложения
 */
import { BinanceWsClient } from './binance.ws-client.js';
import { BybitWsClient } from './bybit.ws-client.js';
import { ALPHA_SYMBOLS, SECONDARY_SYMBOLS, chunkSymbols } from './symbol-groups.js';

let started = false;
const clients: Array<{ start(): void; stop(): void }> = [];

export function startMarketWsLayer() {
  if (started) {
    console.log('[WS_BOOTSTRAP] already started');
    return;
  }
  started = true;

  // Binance: chunk all symbols (alpha + secondary)
  const binanceSymbols = [...ALPHA_SYMBOLS, ...SECONDARY_SYMBOLS];
  const binanceGroups = chunkSymbols(binanceSymbols, 5); // max 5 per stream

  // Bybit: только alpha symbols (более строгий подход)
  const bybitGroups = chunkSymbols(ALPHA_SYMBOLS, 3);

  console.log(`[WS_BOOTSTRAP] Starting Binance WS clients: ${binanceGroups.length} groups`);
  for (const group of binanceGroups) {
    clients.push(new BinanceWsClient(group));
  }

  console.log(`[WS_BOOTSTRAP] Starting Bybit WS clients: ${bybitGroups.length} groups`);
  for (const group of bybitGroups) {
    clients.push(new BybitWsClient(group));
  }

  for (const client of clients) {
    client.start();
  }

  console.log(`[WS_BOOTSTRAP] ✅ Market WS layer started (${clients.length} clients)`);
}

export function stopMarketWsLayer() {
  for (const client of clients) {
    client.stop();
  }
  clients.length = 0;
  started = false;
  console.log('[WS_BOOTSTRAP] Market WS layer stopped');
}
