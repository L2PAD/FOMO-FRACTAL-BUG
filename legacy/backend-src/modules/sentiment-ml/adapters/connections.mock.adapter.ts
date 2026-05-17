/**
 * Mock Connections Adapter
 * ========================
 * 
 * БЛОК 1: Fallback адаптер когда Connections модуль недоступен
 * 
 * ПРИНЦИП:
 * - Все методы возвращают null
 * - Sentiment продолжает работать без enrichment
 * - Используется когда CONNECTIONS_ENABLED=false
 * 
 * ВАЖНО:
 * - Sentiment НЕ падает при отсутствии Connections
 * - Просто работает без author/cluster weighting
 */

import { 
  ConnectionsPort, 
  AuthorProfile, 
  ClusterProfile, 
  NarrativeInfo 
} from '../ports/connections.port.js';

export class MockConnectionsAdapter implements ConnectionsPort {
  private available = false;

  constructor() {
    console.log('[Sentiment] MockConnectionsAdapter initialized - Connections enrichment DISABLED');
  }

  async getAuthorProfile(_authorId: string): Promise<AuthorProfile | null> {
    return null;
  }

  async getClusterProfile(_clusterId: string): Promise<ClusterProfile | null> {
    return null;
  }

  async getNarrative(_symbol: string, _ts: number): Promise<NarrativeInfo | null> {
    return null;
  }

  isAvailable(): boolean {
    return this.available;
  }
}
