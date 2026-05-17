/**
 * Social Intelligence Types
 */
export type SocialEvent = {
  id: string;
  platform: 'twitter' | 'telegram' | 'news';
  authorId: string;
  authorName: string;
  text: string;
  timestamp: number;
  entities: string[];
  tags: string[];
  repostOfId?: string | null;
  quotedEventId?: string | null;
  replyToId?: string | null;
  metrics?: {
    likes?: number;
    reposts?: number;
    replies?: number;
    views?: number;
  };
};

export type SocialCluster = {
  clusterId: string;
  canonicalText: string;
  events: SocialEvent[];
  originEventId: string | null;
  asset: string;
};
