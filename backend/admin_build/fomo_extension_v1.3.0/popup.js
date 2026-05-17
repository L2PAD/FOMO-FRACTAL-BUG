/**
 * FOMO Twitter Connector - Popup Script v1.1
 * Phase 8.3: Final UX Polish
 * 
 * Features:
 * - Preflight check before sync
 * - Explicit sync statuses
 * - API Key guard with show/hide/copy
 * - Human-readable error messages
 * - No auto-close, no auto-retry
 */

// ==================== DOM Elements ====================
const statusContainer = document.getElementById('status-container');
const qualityContainer = document.getElementById('quality-container');
const apiUrlInput = document.getElementById('api-url');
const apiKeyInput = document.getElementById('api-key');
const saveConfigBtn = document.getElementById('save-config-btn');
const configSaved = document.getElementById('config-saved');
const accountList = document.getElementById('account-list');
const syncBtn = document.getElementById('sync-btn');
const checkQualityBtn = document.getElementById('check-quality-btn');
const openPlatformLink = document.getElementById('open-platform');
const openTwitterLink = document.getElementById('open-twitter');
const toggleKeyBtn = document.getElementById('toggle-key-btn');
const copyKeyBtn = document.getElementById('copy-key-btn');
const globalStatusBadge = document.getElementById('global-status');
const globalStatusText = document.getElementById('global-status-text');

// ==================== State ====================
let selectedAccountId = null;
let accounts = [];
let lastQualityReport = null;
let syncStatus = 'IDLE'; // IDLE | CHECKING | READY | SYNCING | SUCCESS | PARTIAL | FAILED
let apiKeyVisible = false;

// ==================== Error Texts (Human-Readable, Soft UX) ====================
const ERROR_TEXTS = {
  NO_COOKIES: {
    title: 'X session not found',
    text: 'Please log in to X (Twitter) first.',
    action: 'Open X, log in, then return here.',
    showTwitterBtn: true,
    icon: '🔐'
  },
  SESSION_EXPIRED: {
    title: 'Session needs refresh',
    text: 'Your X session has expired.',
    action: 'Log in to X to refresh your session.',
    showTwitterBtn: true,
    icon: '🔄'
  },
  API_KEY_INVALID: {
    title: 'API key issue',
    text: 'Please check your API key.',
    action: 'Enter a valid API key from your FOMO dashboard.',
    showKeyFix: true,
    icon: '🔑'
  },
  ACCOUNT_RESTRICTED: {
    title: 'Account needs attention',
    text: 'This X account may have limitations.',
    action: 'Check your account status on X.',
    showTwitterBtn: true,
    icon: '👤'
  },
  NETWORK_ERROR: {
    title: 'Connection issue',
    text: 'Unable to reach FOMO servers.',
    action: 'Check your connection and try again.',
    icon: '📡'
  },
  SERVICE_UNAVAILABLE: {
    title: 'Service busy',
    text: 'The service is temporarily busy.',
    action: 'Please try again in a moment.',
    icon: '⏳'
  },
  PARTIAL_SYNC: {
    title: 'Partial sync completed',
    text: 'Most data synced successfully.',
    action: 'You may sync again later for full coverage.',
    icon: '📊'
  },
  INTERNAL_ERROR: {
    title: 'Unexpected issue',
    text: 'Something didn\'t work as expected.',
    action: 'Please try again.',
    icon: '⚙️'
  }
};

// ==================== Initialize ====================
document.addEventListener('DOMContentLoaded', init);

async function init() {
  updateGlobalStatus('action-required', 'Checking...');
  
  const config = await loadConfig();
  
  if (config.apiUrl) {
    apiUrlInput.value = config.apiUrl;
    openPlatformLink.href = config.apiUrl;
  }
  
  if (config.apiKey) {
    apiKeyInput.value = config.apiKey;
  }
  
  // Event listeners
  saveConfigBtn.addEventListener('click', saveConfig);
  syncBtn.addEventListener('click', handleSync);
  checkQualityBtn.addEventListener('click', refreshAll);
  toggleKeyBtn.addEventListener('click', toggleApiKeyVisibility);
  copyKeyBtn.addEventListener('click', copyApiKey);
  
  // Test Fetch button
  const testFetchBtn = document.getElementById('test-fetch-btn');
  if (testFetchBtn) {
    testFetchBtn.addEventListener('click', handleTestFetch);
  }
  
  openPlatformLink.addEventListener('click', (e) => {
    e.preventDefault();
    const url = apiUrlInput.value || '';
    if (url) chrome.tabs.create({ url });
  });
  
  openTwitterLink.addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: 'https://twitter.com' });
  });
  
  // Auto-save on input (debounced)
  let saveTimeout = null;
  
  apiUrlInput.addEventListener('input', () => {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => autoSaveField('apiUrl', apiUrlInput.value.trim().replace(/\/$/, '')), 500);
  });
  
  apiKeyInput.addEventListener('input', () => {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => autoSaveField('apiKey', apiKeyInput.value.trim()), 500);
  });

  // Initial load
  if (config.apiUrl && config.apiKey) {
    await refreshAll();
  } else {
    showConfigRequired();
    updateGlobalStatus('action-required', 'Setup needed');
  }
}

// ==================== Global Status Badge ====================
function updateGlobalStatus(type, text) {
  globalStatusBadge.className = `status-badge ${type}`;
  globalStatusText.textContent = text;
}

// ==================== API Key Visibility Toggle ====================
function toggleApiKeyVisibility() {
  apiKeyVisible = !apiKeyVisible;
  apiKeyInput.type = apiKeyVisible ? 'text' : 'password';
  toggleKeyBtn.innerHTML = apiKeyVisible 
    ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"></path>
        <line x1="1" y1="1" x2="23" y2="23"></line>
       </svg>`
    : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
        <circle cx="12" cy="12" r="3"></circle>
       </svg>`;
}

async function copyApiKey() {
  const key = apiKeyInput.value;
  if (key) {
    await navigator.clipboard.writeText(key);
    showToast('API key copied');
  }
}

function showToast(message) {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed;
    bottom: 80px;
    left: 50%;
    transform: translateX(-50%);
    background: #1e293b;
    color: white;
    padding: 8px 16px;
    border-radius: 8px;
    font-size: 12px;
    z-index: 1000;
    animation: fadeInOut 2s ease;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2000);
}

// ==================== Refresh All ====================
async function refreshAll() {
  await checkCookieQuality();
  await fetchAccounts();
  determineGlobalStatus();
}

function determineGlobalStatus() {
  if (!lastQualityReport) {
    updateGlobalStatus('checking', 'Checking...');
    return;
  }
  
  if (lastQualityReport.status === 'BLOCKED') {
    updateGlobalStatus('action-required', 'Setup needed');
  } else if (lastQualityReport.status === 'WARNING') {
    updateGlobalStatus('action-required', 'Ready to sync');
  } else if (accounts.length === 0) {
    updateGlobalStatus('action-required', 'Add account');
  } else if (selectedAccountId) {
    const account = accounts.find(a => a.id === selectedAccountId);
    if (account?.sessionStatus === 'OK') {
      updateGlobalStatus('connected', 'Connected');
    } else {
      updateGlobalStatus('action-required', 'Sync needed');
    }
  } else {
    updateGlobalStatus('action-required', 'Select account');
  }
}

// ==================== Preflight Check ====================
async function runPreflightCheck() {
  setSyncStatus('CHECKING');
  showQualityStatus('info', 'Verifying...', 'Checking login and API access.');
  
  const config = await loadConfig();
  
  if (!config.apiUrl || !config.apiKey) {
    setSyncStatus('FAILED');
    showError('API_KEY_INVALID');
    return { ok: false, state: 'API_KEY_INVALID' };
  }
  
  const cookies = await getTwitterCookies();
  
  if (!cookies || cookies.length === 0) {
    setSyncStatus('FAILED');
    showError('NO_COOKIES');
    return { ok: false, state: 'NO_COOKIES' };
  }
  
  try {
    const response = await fetch(`${config.apiUrl}/api/v4/twitter/preflight-check/extension`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ cookies, accountId: selectedAccountId })
    });
    
    if (response.status === 401) {
      setSyncStatus('FAILED');
      showError('API_KEY_INVALID');
      return { ok: false, state: 'API_KEY_INVALID' };
    }
    
    const data = await response.json();
    
    if (!data.ok || data.state !== 'READY') {
      setSyncStatus('FAILED');
      showError(data.state || 'INTERNAL_ERROR', data.fixHint);
      return data;
    }
    
    setSyncStatus('READY');
    showQualityStatus('success', 'Ready to sync', 'X session detected and valid.');
    return data;
    
  } catch (err) {
    setSyncStatus('FAILED');
    showError('NETWORK_ERROR');
    return { ok: false, state: 'NETWORK_ERROR' };
  }
}

// ==================== Main Sync Flow ====================
async function handleSync() {
  if (!selectedAccountId) {
    showStatus('error', 'No Account Selected', 'Please select an account first.');
    return;
  }
  
  // Step 1: Preflight (MANDATORY)
  const preflight = await runPreflightCheck();
  
  if (!preflight.ok) {
    return;
  }
  
  // Step 2: Sync
  await performSync();
}

// ==================== Browser-Native Twitter Fetch ====================
/**
 * Fetch Twitter data directly from browser (THE CORRECT WAY)
 * This ensures Twitter sees real user's IP, cookies, fingerprint
 */
async function fetchTwitterData(type, params) {
  showStatus('info', 'Fetching from X...', 'Making request from your browser...');
  
  try {
    // Verify session first
    const sessionCheck = await window.TwitterFetcher.verifySession();
    if (!sessionCheck.ok || !sessionCheck.valid) {
      showError('SESSION_EXPIRED');
      return { ok: false, error: 'SESSION_EXPIRED' };
    }
    
    let result;
    
    switch (type) {
      case 'SEARCH':
        result = await window.TwitterFetcher.searchTweets(params.keyword, params.limit || 20);
        break;
      case 'PROFILE':
        result = await window.TwitterFetcher.getUserProfile(params.username);
        break;
      default:
        return { ok: false, error: 'Unknown fetch type' };
    }
    
    if (result.ok) {
      showStatus('success', 'Data fetched!', `Got ${result.data?.length || 1} items from X`);
      
      // Send results to backend (backend stores, not fetches!)
      await sendDataToBackend(type, params, result.data);
    } else {
      if (result.error === 'RATE_LIMITED') {
        showError('SERVICE_UNAVAILABLE');
      } else if (result.error === 'SESSION_EXPIRED') {
        showError('SESSION_EXPIRED');
      } else {
        showStatus('neutral', 'Fetch issue', result.error);
      }
    }
    
    return result;
    
  } catch (error) {
    console.error('[FOMO] Twitter fetch error:', error);
    showStatus('neutral', 'Fetch error', error.message);
    return { ok: false, error: error.message };
  }
}

/**
 * Send fetched data to backend (backend = storage only)
 */
async function sendDataToBackend(type, params, data) {
  const config = await loadConfig();
  if (!config.apiUrl || !config.apiKey) return;
  
  try {
    await fetch(`${config.apiUrl}/api/v4/twitter/ingest`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        type,
        params,
        data,
        source: 'browser-extension',
        timestamp: Date.now()
      })
    });
  } catch (e) {
    console.error('[FOMO] Failed to send data to backend:', e);
  }
}

/**
 * Test fetch button handler
 */
async function handleTestFetch() {
  const keyword = prompt('Enter search keyword:', 'bitcoin');
  if (!keyword) return;
  
  await fetchTwitterData('SEARCH', { keyword, limit: 10 });
}

// Expose for inline onclick
window.handleTestFetch = handleTestFetch;

async function performSync() {
  setSyncStatus('SYNCING');
  
  const config = await loadConfig();
  
  try {
    const cookies = await getTwitterCookies();
    const report = lastQualityReport;
    
    const response = await fetch(`${config.apiUrl}/api/v4/twitter/sessions/webhook`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        accountId: selectedAccountId,
        cookies: cookies,
        userAgent: navigator.userAgent + ' FOMO-Extension/1.1',
        qualityReport: report
      })
    });
    
    if (response.status === 401) {
      setSyncStatus('FAILED');
      showError('API_KEY_INVALID');
      return;
    }
    
    const data = await response.json();
    
    if (!response.ok || data.ok === false) {
      const errorInfo = window.BackendErrorMapper?.processBackendError(data);
      
      if (errorInfo) {
        setSyncStatus('FAILED');
        showBackendError(errorInfo);
        updateBadge(errorInfo.canContinue ? 'WARNING' : 'BLOCKED');
        updateGlobalStatus('error', 'Sync failed');
        return;
      }
      
      throw new Error(data.error || data.hint || 'Sync failed');
    }
    
    // Success!
    const isPartial = report && report.status === 'WARNING';
    setSyncStatus(isPartial ? 'PARTIAL' : 'SUCCESS');
    
    if (isPartial) {
      showStatus('soft-warning', 'Session synced', 
        `Session v${data.data?.sessionVersion || '?'} ready. Some cookies may refresh soon.`);
      updateGlobalStatus('connected', 'Connected');
    } else {
      showStatus('success', 'Session synced', 
        'Your X account is connected to FOMO. You can close this window.');
      updateGlobalStatus('connected', 'Connected');
    }
    
    updateBadge('OK');
    await fetchAccounts();
    
  } catch (err) {
    setSyncStatus('FAILED');
    showStatus('error', 'Sync Failed', err.message);
    updateGlobalStatus('error', 'Sync failed');
    updateBadge('BLOCKED');
  }
}

// ==================== Status Management ====================
function setSyncStatus(status) {
  syncStatus = status;
  updateSyncButton();
}

function updateSyncButton() {
  switch (syncStatus) {
    case 'CHECKING':
      syncBtn.disabled = true;
      syncBtn.innerHTML = '<div class="spinner"></div> Checking...';
      break;
    case 'SYNCING':
      syncBtn.disabled = true;
      syncBtn.innerHTML = '<div class="spinner"></div> Syncing...';
      break;
    case 'SUCCESS':
      syncBtn.disabled = true;
      syncBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
        Synced
      `;
      setTimeout(resetSyncButton, 3000);
      break;
    case 'PARTIAL':
      syncBtn.disabled = false;
      syncBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        Sync Again
      `;
      break;
    default:
      resetSyncButton();
  }
}

function resetSyncButton() {
  syncBtn.disabled = !selectedAccountId || (lastQualityReport?.status === 'BLOCKED');
  syncBtn.innerHTML = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"></path>
    </svg>
    Sync Twitter Session
  `;
  
  syncBtn.classList.remove('blocked', 'warning');
  if (lastQualityReport?.status === 'BLOCKED') {
    syncBtn.classList.add('blocked');
  } else if (lastQualityReport?.status === 'WARNING') {
    syncBtn.classList.add('warning');
  }
}

// ==================== Error Display (Soft UX) ====================
function showError(state, customHint = null) {
  const errorConfig = ERROR_TEXTS[state] || ERROR_TEXTS.INTERNAL_ERROR;
  const hint = customHint || errorConfig.action;
  const icon = errorConfig.icon || '⚙️';
  
  let buttonsHtml = '<div style="display: flex; gap: 8px; margin-top: 12px;">';
  
  if (errorConfig.showTwitterBtn) {
    buttonsHtml += `<button class="btn btn-secondary btn-sm" onclick="chrome.tabs.create({url:'https://twitter.com'})">Open X</button>`;
  }
  
  buttonsHtml += `<button class="btn btn-secondary btn-sm" onclick="handleSync()">Try again</button></div>`;
  
  if (errorConfig.showKeyFix) {
    buttonsHtml = `
      <div style="margin-top: 12px;">
        <input type="password" id="api-key-fix" placeholder="Enter new API key" 
          style="width: 100%; padding: 10px; border: 1px solid #475569; border-radius: 8px; margin-bottom: 8px; font-size: 13px; background: #1e293b; color: #f1f5f9;">
        <button class="btn btn-primary btn-sm" onclick="saveAndRetry()">Save & Retry</button>
      </div>
    `;
  }
  
  statusContainer.innerHTML = `
    <div class="backend-error-card neutral">
      <div class="error-header">
        <span class="error-icon">${icon}</span>
        <div class="error-info">
          <div class="error-title">${errorConfig.title}</div>
          <div class="error-message">${errorConfig.text}</div>
        </div>
      </div>
      <div class="error-action">
        <strong>Next step:</strong> ${hint}
      </div>
      ${buttonsHtml}
    </div>
  `;
}

window.saveAndRetry = async function() {
  const newKey = document.getElementById('api-key-fix')?.value?.trim();
  if (newKey) {
    apiKeyInput.value = newKey;
    await autoSaveField('apiKey', newKey);
    clearStatus();
    await handleSync();
  }
};

function showConfigRequired() {
  showQualityStatus('warning', 'Configuration needed', 
    'Enter your FOMO platform URL and API key to get started.');
}

// ==================== Cookie Quality Check ====================
async function checkCookieQuality() {
  showQualityStatus('info', 'Checking session...', 'Analyzing your Twitter cookies...');
  
  try {
    const cookies = await getTwitterCookies();
    const report = window.CookieQualityChecker.checkCookieQuality(cookies);
    const summary = window.CookieQualityChecker.getQualitySummary(report);
    
    lastQualityReport = report;
    renderQualityReport(report, summary);
    updateSyncButtonState(report);
    updateBadge(report.status);
    
    return report;
    
  } catch (err) {
    showQualityStatus('error', 'Check Failed', 'Could not analyze cookies');
    return null;
  }
}

function renderQualityReport(report, summary) {
  let issuesHtml = '';
  
  if (report.issues.length > 0) {
    const errorIssues = report.issues.filter(i => i.severity === 'ERROR');
    const warnIssues = report.issues.filter(i => i.severity === 'WARN');
    
    if (errorIssues.length > 0) {
      issuesHtml += `
        <div class="issues-section">
          <div class="issues-title">Issues Found</div>
          ${errorIssues.map(issue => `
            <div class="issue-item">
              <span class="issue-icon">✕</span>
              <span>${issue.message}</span>
            </div>
          `).join('')}
        </div>
      `;
    }
    
    if (warnIssues.length > 0) {
      issuesHtml += `
        <div class="issues-section">
          <div class="issues-title">Warnings</div>
          ${warnIssues.map(issue => `
            <div class="issue-item">
              <span class="issue-icon">⚠</span>
              <span>${issue.message}</span>
            </div>
          `).join('')}
        </div>
      `;
    }
  }
  
  let stepsHtml = '';
  if (summary.steps.length > 0) {
    stepsHtml = `
      <div class="fix-steps">
        <div class="fix-title">How to fix:</div>
        <ol class="fix-list">
          ${summary.steps.map(step => `<li>${step}</li>`).join('')}
        </ol>
      </div>
    `;
  }
  
  qualityContainer.innerHTML = `
    <div class="quality-card ${summary.color}">
      <div class="quality-header">
        <span class="quality-icon">${summary.icon}</span>
        <div class="quality-info">
          <div class="quality-title">${summary.title}</div>
          <div class="quality-message">${summary.message}</div>
        </div>
      </div>
      ${issuesHtml}
      ${stepsHtml}
    </div>
  `;
}

function showQualityStatus(type, title, message) {
  const icons = { info: '🔍', success: '✓', error: '🔐', warning: '💡', neutral: '📋' };
  const colorMap = { info: 'info', success: 'success', error: 'neutral', warning: 'soft-warning', neutral: 'neutral' };
  qualityContainer.innerHTML = `
    <div class="quality-card ${colorMap[type] || 'info'}">
      <div class="quality-header">
        <span class="quality-icon">${icons[type] || '📋'}</span>
        <div class="quality-info">
          <div class="quality-title">${title}</div>
          <div class="quality-message">${message}</div>
        </div>
      </div>
    </div>
  `;
}

function updateSyncButtonState(report) {
  if (report.status === 'BLOCKED') {
    syncBtn.disabled = true;
    syncBtn.classList.add('blocked');
  } else if (report.status === 'WARNING') {
    syncBtn.disabled = !selectedAccountId;
    syncBtn.classList.remove('blocked');
    syncBtn.classList.add('warning');
  } else {
    syncBtn.disabled = !selectedAccountId;
    syncBtn.classList.remove('blocked', 'warning');
  }
}

function updateBadge(status) {
  chrome.runtime.sendMessage({ type: 'UPDATE_BADGE', status });
}

// ==================== Config Management ====================
async function loadConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['apiUrl', 'apiKey'], (result) => {
      resolve({
        apiUrl: result.apiUrl || '',
        apiKey: result.apiKey || ''
      });
    });
  });
}

async function autoSaveField(fieldName, value) {
  if (!value) return;
  
  return new Promise((resolve) => {
    chrome.storage.local.set({ [fieldName]: value }, () => {
      configSaved.classList.remove('hidden');
      setTimeout(() => configSaved.classList.add('hidden'), 2000);
      
      if (fieldName === 'apiUrl') {
        openPlatformLink.href = value;
      }
      
      resolve();
    });
  });
}

async function saveConfig() {
  const apiUrl = apiUrlInput.value.trim().replace(/\/$/, '');
  const apiKey = apiKeyInput.value.trim();
  
  if (!apiUrl) {
    showStatus('error', 'Invalid URL', 'Please enter your FOMO platform URL.');
    return;
  }
  
  if (!apiKey) {
    showStatus('error', 'Invalid API Key', 'Please enter your API key.');
    return;
  }
  
  return new Promise((resolve) => {
    chrome.storage.local.set({ apiUrl, apiKey }, async () => {
      configSaved.classList.remove('hidden');
      setTimeout(() => configSaved.classList.add('hidden'), 2000);
      
      openPlatformLink.href = apiUrl;
      clearStatus();
      await refreshAll();
      resolve();
    });
  });
}

// ==================== Account Management ====================
async function fetchAccounts() {
  const config = await loadConfig();
  
  if (!config.apiUrl || !config.apiKey) {
    accountList.innerHTML = `
      <div class="quality-card warning">
        <div class="quality-header">
          <span class="quality-icon">⚙️</span>
          <div class="quality-info">
            <div class="quality-title">Configuration needed</div>
            <div class="quality-message">Save your API key first.</div>
          </div>
        </div>
      </div>
    `;
    return;
  }
  
  accountList.innerHTML = `
    <div class="quality-card info">
      <div class="quality-header">
        <span class="quality-icon">⏳</span>
        <div class="quality-info">
          <div class="quality-title">Loading accounts...</div>
          <div class="quality-message">Please wait</div>
        </div>
      </div>
    </div>
  `;
  
  try {
    // Include legacy (admin) accounts for extension
    const url = `${config.apiUrl}/api/v4/twitter/accounts?includeLegacy=true`;
    console.log('[FOMO Debug] Fetching accounts from:', url);
    console.log('[FOMO Debug] API Key prefix:', config.apiKey?.substring(0, 15) + '...');
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json'
      }
    });
    
    console.log('[FOMO Debug] Response status:', response.status);
    
    if (response.status === 401) {
      showError('API_KEY_INVALID');
      accountList.innerHTML = '';
      return;
    }
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    console.log('[FOMO Debug] Response data:', JSON.stringify(data));
    
    if (!data.ok) {
      throw new Error(data.error || 'Failed to fetch accounts');
    }
    
    accounts = data.data?.accounts || [];
    console.log('[FOMO Debug] Accounts found:', accounts.length);
    
    if (accounts.length === 0) {
      accountList.innerHTML = `
        <div class="quality-card warning">
          <div class="quality-header">
            <span class="quality-icon">📭</span>
            <div class="quality-info">
              <div class="quality-title">No accounts found</div>
              <div class="quality-message">Add a Twitter account in the FOMO dashboard first.</div>
            </div>
          </div>
        </div>
      `;
      syncBtn.disabled = true;
      return;
    }
    
    renderAccounts();
    clearStatus();
    
  } catch (err) {
    accountList.innerHTML = `
      <div class="quality-card error">
        <div class="quality-header">
          <span class="quality-icon">❌</span>
          <div class="quality-info">
            <div class="quality-title">Failed to load accounts</div>
            <div class="quality-message">${err.message}</div>
          </div>
        </div>
      </div>
    `;
    syncBtn.disabled = true;
  }
}

function renderAccounts() {
  accountList.innerHTML = accounts.map(account => {
    const statusClass = getStatusClass(account.sessionStatus);
    const statusLabel = getStatusLabel(account.sessionStatus);
    const isSelected = selectedAccountId === account.id;
    
    return `
      <div class="account-item ${isSelected ? 'selected' : ''}" data-id="${account.id}">
        <span class="username">@${account.username}</span>
        <span class="status ${statusClass}">${statusLabel}</span>
      </div>
    `;
  }).join('');
  
  accountList.querySelectorAll('.account-item').forEach(item => {
    item.addEventListener('click', () => selectAccount(item.dataset.id));
  });
  
  if (!selectedAccountId) {
    const needsRefresh = accounts.find(a => a.sessionStatus !== 'OK');
    const firstAccount = needsRefresh || accounts[0];
    if (firstAccount) selectAccount(firstAccount.id);
  }
}

function getStatusClass(status) {
  switch (status) {
    case 'OK': return 'ok';
    case 'STALE': return 'stale';
    case 'INVALID': return 'invalid';
    default: return 'no-session';
  }
}

function getStatusLabel(status) {
  switch (status) {
    case 'OK': return 'Active';
    case 'STALE': return 'Refresh soon';
    case 'INVALID': return 'Needs login';
    default: return 'Not synced';
  }
}

function selectAccount(accountId) {
  selectedAccountId = accountId;
  
  accountList.querySelectorAll('.account-item').forEach(item => {
    item.classList.toggle('selected', item.dataset.id === accountId);
  });
  
  if (lastQualityReport) {
    updateSyncButtonState(lastQualityReport);
  } else {
    syncBtn.disabled = false;
  }
  
  determineGlobalStatus();
}

// ==================== Cookies ====================
async function getTwitterCookies() {
  return new Promise((resolve) => {
    const cookiePromises = [
      new Promise(r => chrome.cookies.getAll({ domain: '.twitter.com' }, r)),
      new Promise(r => chrome.cookies.getAll({ domain: '.x.com' }, r))
    ];
    
    Promise.all(cookiePromises).then(([twitterCookies, xCookies]) => {
      const allCookies = [...twitterCookies, ...xCookies];
      const uniqueCookies = [];
      const seen = new Set();
      
      for (const cookie of allCookies) {
        const key = `${cookie.name}:${cookie.domain}`;
        if (!seen.has(key)) {
          seen.add(key);
          uniqueCookies.push({
            name: cookie.name,
            value: cookie.value,
            domain: cookie.domain,
            path: cookie.path,
            secure: cookie.secure,
            httpOnly: cookie.httpOnly,
            sameSite: cookie.sameSite,
            expirationDate: cookie.expirationDate
          });
        }
      }
      
      resolve(uniqueCookies);
    });
  });
}

// ==================== Status Display ====================
function showStatus(type, title, message) {
  statusContainer.innerHTML = `
    <div class="status-card ${type}">
      <div class="title">${title}</div>
      <div class="message">${message}</div>
    </div>
  `;
}

function showBackendError(errorInfo) {
  const retryHtml = errorInfo.retryAfter 
    ? `<div style="margin-top: 8px; font-size: 11px; color: #64748b;">Try again in ${errorInfo.retryAfter} minute${errorInfo.retryAfter > 1 ? 's' : ''}</div>`
    : '';
  
  statusContainer.innerHTML = `
    <div class="backend-error-card ${errorInfo.color}">
      <div class="error-header">
        <span class="error-icon">${errorInfo.icon}</span>
        <div class="error-info">
          <div class="error-title">${errorInfo.title}</div>
          <div class="error-message">${errorInfo.message}</div>
        </div>
      </div>
      <div class="error-action">
        <strong>What to do:</strong> ${errorInfo.action}
      </div>
      ${retryHtml}
      ${errorInfo.showRetry ? '<button class="btn btn-secondary btn-sm" style="margin-top: 12px;" onclick="handleSync()">Try Again</button>' : ''}
    </div>
  `;
}

function clearStatus() {
  statusContainer.innerHTML = '';
}
