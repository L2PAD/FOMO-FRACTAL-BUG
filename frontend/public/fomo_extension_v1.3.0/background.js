/**
 * FOMO Twitter Sync - Background Service Worker
 * Handles background tasks like badge updates and cookie retrieval
 * 
 * Chrome Web Store compliant - minimal permissions
 */

// Listen for installation
chrome.runtime.onInstalled.addListener((details) => {
  // Set default config if first install
  if (details.reason === 'install') {
    chrome.storage.local.set({
      apiUrl: '',
      apiKey: ''
    });
  }
  
  // Set initial badge
  updateBadge('none');
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_COOKIES') {
    // Get cookies from Twitter/X domains
    Promise.all([
      chrome.cookies.getAll({ domain: '.twitter.com' }),
      chrome.cookies.getAll({ domain: '.x.com' })
    ]).then(([twitterCookies, xCookies]) => {
      const allCookies = [...twitterCookies, ...xCookies];
      sendResponse({ cookies: allCookies });
    });
    return true; // Keep channel open for async response
  }
  
  if (message.type === 'UPDATE_BADGE') {
    updateBadge(message.status);
    sendResponse({ ok: true });
  }
});

// Badge management based on cookie quality status
function updateBadge(status) {
  const badgeConfig = {
    'OK': { text: '✓', color: '#22c55e' },
    'WARNING': { text: '!', color: '#f59e0b' },
    'BLOCKED': { text: '✕', color: '#ef4444' },
    'ok': { text: '✓', color: '#22c55e' },
    'stale': { text: '!', color: '#f59e0b' },
    'error': { text: '✕', color: '#ef4444' },
    'none': { text: '', color: '#6b7280' }
  };
  
  const config = badgeConfig[status] || badgeConfig.none;
  chrome.action.setBadgeText({ text: config.text });
  chrome.action.setBadgeBackgroundColor({ color: config.color });
}

// Initial badge state
updateBadge('none');
