/**
 * Connections Port Interface
 * ==========================
 * 
 * БЛОК 1: Архитектурная врезка Connections → Sentiment
 * 
 * ПРИНЦИП:
 * - Sentiment НЕ импортирует модели Connections напрямую
 * - Sentiment видит только этот интерфейс
 * - Реализация может быть:
 *   - ConnectionsAdapter (прод)
 *   - MockConnectionsAdapter (тест/fallback)
 * 
 * ЗАПРЕТ:
 * - ❌ Прямой импорт из connections-proxy
 * - ❌ Прямое чтение connections_db
 * - ❌ Shared schema
 */

export interface AuthorProfile {
  authorScore: number;      // 0..1 — общий score автора
  botProb: number;          // 0..1 — вероятность бота
  influence: number;        // 0..1 — влиятельность
  hitRate1d?: number;       // Hit rate на 1D horizon
  hitRate7d?: number;       // Hit rate на 7D horizon
  hitRate30d?: number;      // Hit rate на 30D horizon
  clusterId?: string;       // ID кластера (если есть)
  categories?: string[];    // Категории: KOL, ANALYST, VC, etc.
}

export interface ClusterProfile {
  clusterScore: number;       // 0..1 — общий score кластера
  manipulationProb: number;   // 0..1 — вероятность координированной манипуляции
  memberCount?: number;       // Количество участников
  avgInfluence?: number;      // Средняя влиятельность
}

export interface NarrativeInfo {
  narrativeId?: string;                     // ID нарратива
  heat: number;                             // 0..1 — текущий "накал"
  phase: 'EARLY' | 'MID' | 'LATE' | 'DEAD'; // Фаза жизненного цикла
  mentionCount?: number;                    // Количество упоминаний
  topTokens?: string[];                     // Связанные токены
}

/**
 * ConnectionsPort — интерфейс для интеграции с Connections модулем
 * 
 * Все методы возвращают null при недоступности данных (graceful fallback)
 */
export interface ConnectionsPort {
  /**
   * Получить профиль автора по ID
   * @param authorId - Twitter handle или ID
   * @returns AuthorProfile или null
   */
  getAuthorProfile(authorId: string): Promise<AuthorProfile | null>;

  /**
   * Получить профиль кластера по ID
   * @param clusterId - ID кластера
   * @returns ClusterProfile или null
   */
  getClusterProfile(clusterId: string): Promise<ClusterProfile | null>;

  /**
   * Получить информацию о нарративе для символа
   * @param symbol - Символ токена (BTC, ETH, etc.)
   * @param ts - Timestamp
   * @returns NarrativeInfo или null
   */
  getNarrative(symbol: string, ts: number): Promise<NarrativeInfo | null>;

  /**
   * Проверить доступность Connections модуля
   */
  isAvailable(): boolean;
}
