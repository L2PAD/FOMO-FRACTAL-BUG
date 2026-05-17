/**
 * FOMO Twitter Fetcher - Browser-Native Twitter API Client
 * 
 * CRITICAL: All Twitter requests MUST happen in browser context
 * This ensures Twitter sees real user's IP, cookies, fingerprint
 * 
 * Backend NEVER touches Twitter directly!
 */

const TwitterFetcher = {
  // GraphQL endpoint IDs (may change, but we try latest known)
  ENDPOINTS: {
    SearchTimeline: 'IzA05zAvo7MGeZrkQmIVvw/SearchTimeline',
    UserByScreenName: '1VOOyvKkiI3FMmkeDNxM9A/UserByScreenName',
    UserTweets: 'CdG2Vuc1vjkPLHf-FMU_dA/UserTweets',
  },
  
  GQL_URL: 'https://x.com/i/api/graphql',
  ADAPTIVE_URL: 'https://x.com/i/api/2/search/adaptive.json',
  
  /**
   * Get CSRF token from cookies
   */
  async getCsrfToken() {
    const cookies = await chrome.cookies.getAll({ domain: '.x.com' });
    const ct0 = cookies.find(c => c.name === 'ct0');
    return ct0?.value || null;
  },
  
  /**
   * Build headers for Twitter API requests
   */
  async buildHeaders() {
    const csrfToken = await this.getCsrfToken();
    
    if (!csrfToken) {
      throw new Error('NO_CSRF_TOKEN');
    }
    
    return {
      'accept': '*/*',
      'accept-language': 'en-US,en;q=0.9',
      'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
      'content-type': 'application/json',
      'x-csrf-token': csrfToken,
      'x-twitter-auth-type': 'OAuth2Session',
      'x-twitter-active-user': 'yes',
      'x-twitter-client-language': 'en',
    };
  },
  
  /**
   * Search tweets by keyword
   * @param {string} keyword - Search query
   * @param {number} limit - Max results (default 20)
   * @returns {Promise<{ok: boolean, data?: any, error?: string}>}
   */
  async searchTweets(keyword, limit = 20) {
    try {
      const headers = await this.buildHeaders();
      
      // Try GraphQL first
      const gqlResult = await this.searchWithGraphQL(keyword, limit, headers);
      if (gqlResult.ok && gqlResult.data?.length > 0) {
        return gqlResult;
      }
      
      // Fallback to adaptive
      console.log('[TwitterFetcher] GraphQL empty/failed, trying adaptive...');
      return await this.searchWithAdaptive(keyword, limit, headers);
      
    } catch (error) {
      console.error('[TwitterFetcher] Search error:', error);
      return { ok: false, error: error.message };
    }
  },
  
  /**
   * Search using GraphQL SearchTimeline
   */
  async searchWithGraphQL(keyword, limit, headers) {
    const url = `${this.GQL_URL}/${this.ENDPOINTS.SearchTimeline}`;
    
    const variables = {
      rawQuery: keyword,
      count: limit,
      querySource: 'typed_query',
      product: 'Latest'
    };
    
    const features = {
      rweb_tipjar_consumption_enabled: true,
      responsive_web_graphql_exclude_directive_enabled: true,
      verified_phone_label_enabled: false,
      creator_subscriptions_tweet_preview_api_enabled: true,
      responsive_web_graphql_timeline_navigation_enabled: true,
      responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
      communities_web_enable_tweet_community_results_fetch: true,
      c9s_tweet_anatomy_moderator_badge_enabled: true,
      articles_preview_enabled: true,
      responsive_web_edit_tweet_api_enabled: true,
      graphql_is_translatable_rweb_tweet_is_translatable_enabled: true,
      view_counts_everywhere_api_enabled: true,
      longform_notetweets_consumption_enabled: true,
      responsive_web_twitter_article_tweet_consumption_enabled: true,
      tweet_awards_web_tipping_enabled: false,
      creator_subscriptions_quote_tweet_preview_enabled: false,
      freedom_of_speech_not_reach_fetch_enabled: true,
      standardized_nudges_misinfo: true,
      tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled: true,
      rweb_video_timestamps_enabled: true,
      longform_notetweets_rich_text_read_enabled: true,
      longform_notetweets_inline_media_enabled: true,
      responsive_web_enhance_cards_enabled: false
    };
    
    const params = new URLSearchParams({
      variables: JSON.stringify(variables),
      features: JSON.stringify(features)
    });
    
    try {
      const response = await fetch(`${url}?${params}`, {
        method: 'GET',
        headers,
        credentials: 'include' // CRITICAL: sends cookies automatically
      });
      
      if (response.status === 429) {
        return { ok: false, error: 'RATE_LIMITED', status: 429 };
      }
      
      if (response.status === 401 || response.status === 403) {
        return { ok: false, error: 'SESSION_EXPIRED', status: response.status };
      }
      
      if (!response.ok) {
        return { ok: false, error: `GraphQL error: ${response.status}` };
      }
      
      const data = await response.json();
      const tweets = this.parseGraphQLTweets(data);
      
      return { ok: true, data: tweets, source: 'graphql' };
      
    } catch (error) {
      return { ok: false, error: error.message };
    }
  },
  
  /**
   * Search using Adaptive Search API (fallback)
   */
  async searchWithAdaptive(keyword, limit, headers) {
    const params = new URLSearchParams({
      include_profile_interstitial_type: '1',
      include_blocking: '1',
      include_blocked_by: '1',
      include_followed_by: '1',
      include_want_retweets: '1',
      include_mute_edge: '1',
      include_can_dm: '1',
      include_can_media_tag: '1',
      include_ext_is_blue_verified: '1',
      include_ext_verified_type: '1',
      skip_status: '1',
      cards_platform: 'Web-12',
      include_cards: '1',
      include_ext_alt_text: 'true',
      include_quote_count: 'true',
      include_reply_count: '1',
      tweet_mode: 'extended',
      include_ext_views: 'true',
      include_entities: 'true',
      include_user_entities: 'true',
      q: keyword,
      count: String(limit),
      query_source: 'typed_query',
      pc: '1',
      spelling_corrections: '1'
    });
    
    try {
      const response = await fetch(`${this.ADAPTIVE_URL}?${params}`, {
        method: 'GET',
        headers,
        credentials: 'include'
      });
      
      if (response.status === 429) {
        return { ok: false, error: 'RATE_LIMITED', status: 429 };
      }
      
      if (response.status === 401 || response.status === 403) {
        return { ok: false, error: 'SESSION_EXPIRED', status: response.status };
      }
      
      if (!response.ok) {
        return { ok: false, error: `Adaptive error: ${response.status}` };
      }
      
      const text = await response.text();
      if (!text || text.length < 10) {
        return { ok: false, error: 'EMPTY_RESPONSE' };
      }
      
      const data = JSON.parse(text);
      const tweets = this.parseAdaptiveTweets(data, limit);
      
      return { ok: true, data: tweets, source: 'adaptive' };
      
    } catch (error) {
      return { ok: false, error: error.message };
    }
  },
  
  /**
   * Parse tweets from GraphQL response
   */
  parseGraphQLTweets(data) {
    const tweets = [];
    
    try {
      const instructions = data?.data?.search_by_raw_query?.search_timeline?.timeline?.instructions || [];
      
      for (const instruction of instructions) {
        if (instruction.type === 'TimelineAddEntries') {
          for (const entry of instruction.entries || []) {
            const tweet = this.extractTweetFromEntry(entry);
            if (tweet) tweets.push(tweet);
          }
        }
      }
    } catch (e) {
      console.error('[TwitterFetcher] GraphQL parse error:', e);
    }
    
    return tweets;
  },
  
  /**
   * Extract tweet data from timeline entry
   */
  extractTweetFromEntry(entry) {
    try {
      const content = entry?.content;
      if (!content) return null;
      
      let tweetResult = null;
      
      if (content.itemContent?.tweet_results?.result) {
        tweetResult = content.itemContent.tweet_results.result;
      } else if (content.entryType === 'TimelineTimelineItem') {
        tweetResult = content.itemContent?.tweet_results?.result;
      }
      
      if (!tweetResult) return null;
      
      // Handle tweet with visibility results
      if (tweetResult.__typename === 'TweetWithVisibilityResults') {
        tweetResult = tweetResult.tweet;
      }
      
      const legacy = tweetResult.legacy;
      const core = tweetResult.core?.user_results?.result;
      const userLegacy = core?.legacy;
      
      if (!legacy) return null;
      
      return {
        id: legacy.id_str || tweetResult.rest_id,
        text: legacy.full_text || legacy.text,
        createdAt: legacy.created_at,
        likes: legacy.favorite_count || 0,
        reposts: legacy.retweet_count || 0,
        replies: legacy.reply_count || 0,
        views: tweetResult.views?.count || 0,
        author: {
          username: userLegacy?.screen_name || '',
          name: userLegacy?.name || '',
          verified: userLegacy?.verified || core?.is_blue_verified || false,
          followers: userLegacy?.followers_count || 0
        }
      };
    } catch (e) {
      return null;
    }
  },
  
  /**
   * Parse tweets from Adaptive response
   */
  parseAdaptiveTweets(data, limit) {
    const tweets = [];
    const globalTweets = data?.globalObjects?.tweets || {};
    const globalUsers = data?.globalObjects?.users || {};
    
    for (const [tweetId, tweet] of Object.entries(globalTweets)) {
      if (tweets.length >= limit) break;
      
      const userId = tweet.user_id_str;
      const user = globalUsers[userId] || {};
      
      tweets.push({
        id: tweet.id_str || tweetId,
        text: tweet.full_text || tweet.text || '',
        createdAt: tweet.created_at,
        likes: tweet.favorite_count || 0,
        reposts: tweet.retweet_count || 0,
        replies: tweet.reply_count || 0,
        views: tweet.ext_views?.count || 0,
        author: {
          username: user.screen_name || '',
          name: user.name || '',
          verified: user.verified || user.ext_is_blue_verified || false,
          followers: user.followers_count || 0
        }
      });
    }
    
    return tweets;
  },
  
  /**
   * Get user profile by username
   */
  async getUserProfile(username) {
    try {
      const headers = await this.buildHeaders();
      const url = `${this.GQL_URL}/${this.ENDPOINTS.UserByScreenName}`;
      
      const variables = {
        screen_name: username,
        withSafetyModeUserFields: true
      };
      
      const features = {
        hidden_profile_subscriptions_enabled: true,
        rweb_tipjar_consumption_enabled: true,
        responsive_web_graphql_exclude_directive_enabled: true,
        verified_phone_label_enabled: false,
        subscriptions_verification_info_is_identity_verified_enabled: true,
        subscriptions_verification_info_verified_since_enabled: true,
        highlights_tweets_tab_ui_enabled: true,
        responsive_web_twitter_article_notes_tab_enabled: true,
        subscriptions_feature_can_gift_premium: true,
        creator_subscriptions_tweet_preview_api_enabled: true,
        responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
        responsive_web_graphql_timeline_navigation_enabled: true
      };
      
      const params = new URLSearchParams({
        variables: JSON.stringify(variables),
        features: JSON.stringify(features)
      });
      
      const response = await fetch(`${url}?${params}`, {
        method: 'GET',
        headers,
        credentials: 'include'
      });
      
      if (!response.ok) {
        return { ok: false, error: `Profile fetch failed: ${response.status}` };
      }
      
      const data = await response.json();
      const user = data?.data?.user?.result?.legacy;
      
      if (!user) {
        return { ok: false, error: 'User not found' };
      }
      
      return {
        ok: true,
        data: {
          username: user.screen_name,
          name: user.name,
          bio: user.description,
          followers: user.followers_count,
          following: user.friends_count,
          tweets: user.statuses_count,
          verified: user.verified || data?.data?.user?.result?.is_blue_verified,
          avatar: user.profile_image_url_https
        }
      };
      
    } catch (error) {
      return { ok: false, error: error.message };
    }
  },
  
  /**
   * Verify session is valid (can make authenticated requests)
   */
  async verifySession() {
    try {
      const headers = await this.buildHeaders();
      
      // Simple request to check if session works
      const response = await fetch('https://x.com/i/api/1.1/account/settings.json', {
        method: 'GET',
        headers,
        credentials: 'include'
      });
      
      if (response.ok) {
        return { ok: true, valid: true };
      }
      
      if (response.status === 401 || response.status === 403) {
        return { ok: true, valid: false, reason: 'SESSION_EXPIRED' };
      }
      
      return { ok: true, valid: false, reason: `HTTP_${response.status}` };
      
    } catch (error) {
      return { ok: false, error: error.message };
    }
  }
};

// Export for use in popup.js
window.TwitterFetcher = TwitterFetcher;
