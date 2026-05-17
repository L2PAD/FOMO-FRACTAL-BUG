/**
 * PHASE 2.1 — AI Cookie Quality Check
 * 
 * Deterministic checks for Twitter session cookies quality.
 * Works locally without backend dependency.
 * 
 * Checks:
 * - P0: Required cookies presence (auth_token, ct0, twid)
 * - P0: Auth validity (not expired, not deleted)
 * - P1: Expiration check (expired, expiring soon)
 * - P1: sameSite compatibility
 * - P2: Cookie count heuristic
 */

// Required cookies for Twitter authentication
const REQUIRED_COOKIES = ['auth_token', 'ct0', 'twid'];

// Minimum auth_token length
const AUTH_TOKEN_MIN_LENGTH = 30;

// Cookie count thresholds
const COOKIE_COUNT_MIN = 5;
const COOKIE_COUNT_WARN = 10;

// Expiration warning threshold (24 hours in ms)
const EXPIRATION_WARNING_MS = 24 * 60 * 60 * 1000;

/**
 * @typedef {Object} CookieIssue
 * @property {string} code - Issue code
 * @property {'ERROR' | 'WARN'} severity - Issue severity
 * @property {string} message - Human-readable message
 * @property {string} [fix] - How to fix the issue
 */

/**
 * @typedef {Object} CookieQualityReport
 * @property {'OK' | 'WARNING' | 'BLOCKED'} status - Overall status
 * @property {number} cookieCount - Number of cookies found
 * @property {CookieIssue[]} issues - List of issues found
 * @property {Object} details - Detailed check results
 */

/**
 * Run all quality checks on cookies
 * @param {Array} cookies - Array of cookie objects
 * @returns {CookieQualityReport}
 */
function checkCookieQuality(cookies) {
  const issues = [];
  const details = {
    requiredCookies: {},
    authToken: null,
    ct0: null,
    expiration: {
      expired: [],
      expiringSoon: []
    },
    sameSiteIssues: [],
    cookieCount: cookies.length
  };

  // === P0: Required Cookies Check ===
  for (const name of REQUIRED_COOKIES) {
    const cookie = cookies.find(c => c.name === name);
    details.requiredCookies[name] = cookie ? 'found' : 'missing';
    
    if (!cookie) {
      issues.push({
        code: 'MISSING_REQUIRED_COOKIE',
        severity: 'ERROR',
        message: `Required cookie "${name}" is missing`,
        fix: 'Log in to Twitter/X in this browser'
      });
    } else if (!cookie.value || cookie.value.trim() === '') {
      issues.push({
        code: 'EMPTY_REQUIRED_COOKIE',
        severity: 'ERROR',
        message: `Required cookie "${name}" is empty`,
        fix: 'Log out and log back in to Twitter/X'
      });
    }
  }

  // === P0: Auth Token Validity ===
  const authToken = cookies.find(c => c.name === 'auth_token');
  if (authToken) {
    details.authToken = {
      length: authToken.value?.length || 0,
      hasExpiration: !!authToken.expirationDate
    };

    // Check if auth_token is too short (likely invalid)
    if (authToken.value && authToken.value.length < AUTH_TOKEN_MIN_LENGTH) {
      issues.push({
        code: 'AUTH_INVALID',
        severity: 'ERROR',
        message: 'Authentication token appears invalid (too short)',
        fix: 'Log out and log back in to Twitter/X'
      });
    }

    // Check if auth_token is expired
    if (authToken.expirationDate) {
      const expiresAt = authToken.expirationDate * 1000; // Convert to ms
      const now = Date.now();
      
      if (expiresAt < now) {
        issues.push({
          code: 'AUTH_EXPIRED',
          severity: 'ERROR',
          message: 'Authentication token has expired',
          fix: 'Log out and log back in to Twitter/X'
        });
      }
    }

    // Check for "deleted" marker (some browsers set value to "deleted")
    if (authToken.value === 'deleted' || authToken.value === '') {
      issues.push({
        code: 'AUTH_DELETED',
        severity: 'ERROR',
        message: 'Authentication token was deleted',
        fix: 'Log in to Twitter/X again'
      });
    }
  }

  // === P0: CT0 Token Validity ===
  const ct0 = cookies.find(c => c.name === 'ct0');
  if (ct0) {
    details.ct0 = {
      length: ct0.value?.length || 0
    };

    // CT0 should be a hex string of specific length
    if (ct0.value && ct0.value.length < 32) {
      issues.push({
        code: 'CT0_INVALID',
        severity: 'ERROR',
        message: 'CSRF token appears invalid',
        fix: 'Refresh Twitter/X page while logged in'
      });
    }
  }

  // === P1: Expiration Check ===
  const now = Date.now();
  for (const cookie of cookies) {
    if (!cookie.expirationDate) {
      // Session cookie (no expiration) - this is OK
      continue;
    }

    const expiresAt = cookie.expirationDate * 1000;
    
    if (expiresAt < now) {
      details.expiration.expired.push(cookie.name);
    } else if (expiresAt < now + EXPIRATION_WARNING_MS) {
      details.expiration.expiringSoon.push(cookie.name);
    }
  }

  // Important cookies expiring soon
  const importantExpiring = details.expiration.expiringSoon.filter(
    name => REQUIRED_COOKIES.includes(name)
  );
  if (importantExpiring.length > 0) {
    issues.push({
      code: 'COOKIES_EXPIRING_SOON',
      severity: 'WARN',
      message: `Important cookies expiring within 24h: ${importantExpiring.join(', ')}`,
      fix: 'Re-login to Twitter/X to refresh cookies'
    });
  }

  // === P1: sameSite Compatibility ===
  for (const cookie of cookies) {
    // Playwright may have issues with certain sameSite values
    if (cookie.sameSite === 'no_restriction' || cookie.sameSite === 'unspecified') {
      details.sameSiteIssues.push(cookie.name);
    }
  }

  // Only warn if critical cookies have sameSite issues
  const criticalSameSiteIssues = details.sameSiteIssues.filter(
    name => REQUIRED_COOKIES.includes(name)
  );
  if (criticalSameSiteIssues.length > 0) {
    issues.push({
      code: 'SAMESITE_COMPATIBILITY',
      severity: 'WARN',
      message: `Some cookies may have compatibility issues: ${criticalSameSiteIssues.join(', ')}`,
      fix: 'This may affect parsing stability'
    });
  }

  // === P2: Cookie Count Heuristic ===
  if (cookies.length === 0) {
    issues.push({
      code: 'NO_COOKIES',
      severity: 'ERROR',
      message: 'No cookies found',
      fix: 'Make sure you are logged into Twitter/X'
    });
  } else if (cookies.length < COOKIE_COUNT_MIN) {
    issues.push({
      code: 'LOW_COOKIE_COUNT',
      severity: 'ERROR',
      message: `Very few cookies found (${cookies.length}), session may be incomplete`,
      fix: 'Log in to Twitter/X and browse a few pages before syncing'
    });
  } else if (cookies.length < COOKIE_COUNT_WARN) {
    issues.push({
      code: 'LOW_COOKIE_COUNT_WARN',
      severity: 'WARN',
      message: `Found ${cookies.length} cookies, which is lower than typical (10-25)`,
      fix: 'Session may work but could be unstable'
    });
  }

  // === Determine Overall Status ===
  const hasErrors = issues.some(i => i.severity === 'ERROR');
  const hasWarnings = issues.some(i => i.severity === 'WARN');

  let status;
  if (hasErrors) {
    status = 'BLOCKED';
  } else if (hasWarnings) {
    status = 'WARNING';
  } else {
    status = 'OK';
  }

  return {
    status,
    cookieCount: cookies.length,
    issues,
    details
  };
}

/**
 * Get UX-friendly summary for the report
 * @param {CookieQualityReport} report
 * @returns {Object} UX-friendly summary
 */
function getQualitySummary(report) {
  switch (report.status) {
    case 'BLOCKED':
      return {
        icon: '🔐',
        title: 'Session needs attention',
        message: 'Please log in to X to connect your session.',
        color: 'neutral',
        canContinue: false,
        steps: [
          'Open X (twitter.com) in this browser',
          'Log in to your account',
          'Return here and tap Sync'
        ]
      };
    
    case 'WARNING':
      return {
        icon: '💡',
        title: 'Session ready with notes',
        message: 'You can sync now. Some cookies may refresh soon.',
        color: 'soft-warning',
        canContinue: true,
        steps: [
          'You can sync now',
          'For best results, re-login to X periodically'
        ]
      };
    
    case 'OK':
    default:
      return {
        icon: '✓',
        title: 'Session ready',
        message: `${report.cookieCount} cookies detected. Ready to sync.`,
        color: 'success',
        canContinue: true,
        steps: []
      };
  }
}

// Export for use in popup.js
if (typeof window !== 'undefined') {
  window.CookieQualityChecker = {
    checkCookieQuality,
    getQualitySummary,
    REQUIRED_COOKIES
  };
}
