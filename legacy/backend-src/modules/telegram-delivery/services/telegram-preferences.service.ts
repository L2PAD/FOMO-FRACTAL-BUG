/**
 * Telegram Preferences Service
 *
 * Stores and applies user prediction alert preferences.
 * Uses intelligence_engine.prediction_telegram_prefs collection.
 */

import { MongoClient } from 'mongodb';
import type { PredictionTelegramPrefs } from '../types/telegram.types.js';

const MONGO_URL = process.env.MONGO_URL || 'mongodb://localhost:27017';
const DB_NAME = process.env.DB_NAME || 'intelligence_engine';

const DEFAULT_PREFS: Omit<PredictionTelegramPrefs, 'chatId' | 'createdAt' | 'updatedAt'> = {
  enabled: true,
  instantHighAlerts: true,
  batchDigest30m: true,
  weeklyDigest: true,
  highOnly: false,
  muteUntil: null,
  maxMessagesPerHour: 10,
};

class TelegramPreferencesService {
  async getPrefs(chatId: string): Promise<PredictionTelegramPrefs | null> {
    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const doc = await client.db(DB_NAME)
        .collection('prediction_telegram_prefs')
        .findOne({ chatId }, { projection: { _id: 0 } });
      return doc as PredictionTelegramPrefs | null;
    } finally {
      await client.close();
    }
  }

  async getOrCreate(chatId: string): Promise<PredictionTelegramPrefs> {
    const existing = await this.getPrefs(chatId);
    if (existing) return existing;

    const now = new Date().toISOString();
    const prefs: PredictionTelegramPrefs = {
      ...DEFAULT_PREFS,
      chatId,
      createdAt: now,
      updatedAt: now,
    };

    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      await client.db(DB_NAME)
        .collection('prediction_telegram_prefs')
        .insertOne({ ...prefs });
    } finally {
      await client.close();
    }

    return prefs;
  }

  async updatePrefs(chatId: string, updates: Partial<PredictionTelegramPrefs>): Promise<PredictionTelegramPrefs> {
    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const now = new Date().toISOString();
      await client.db(DB_NAME)
        .collection('prediction_telegram_prefs')
        .updateOne(
          { chatId },
          { $set: { ...updates, updatedAt: now } },
          { upsert: true },
        );
      return (await this.getPrefs(chatId))!;
    } finally {
      await client.close();
    }
  }

  async getAllEnabled(): Promise<PredictionTelegramPrefs[]> {
    const client = new MongoClient(MONGO_URL);
    try {
      await client.connect();
      const docs = await client.db(DB_NAME)
        .collection('prediction_telegram_prefs')
        .find({ enabled: true }, { projection: { _id: 0 } })
        .toArray();
      return docs as PredictionTelegramPrefs[];
    } finally {
      await client.close();
    }
  }

  isMuted(prefs: PredictionTelegramPrefs): boolean {
    if (!prefs.muteUntil) return false;
    return Date.now() < prefs.muteUntil;
  }
}

export const telegramPreferencesService = new TelegramPreferencesService();
