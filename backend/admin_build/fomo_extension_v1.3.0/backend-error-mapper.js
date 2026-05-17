/**
 * PHASE 2.2 — Human Error Mapping
 * 
 * Translates backend error codes to human-readable messages.
 * This runs in Chrome Extension - NO backend dependency.
 * 
 * Backend sends: { errorCode: 'SESSION_INVALID', severity: 'BLOCKED', meta: {...} }
 * Extension shows: "You are logged out of Twitter..."
 */

/**
 * Error mapping structure
 * @typedef {Object} ErrorMapping
 * @property {string} title - Short title
 * @property {string} message - Explanation
 * @property {string} action - What user should do
 * @property {'INFO' | 'WARNING' | 'BLOCKED'} level - UI severity
 * @property {number} [retryAfter] - Suggested wait time in minutes
 */

const ERROR_MAP = {
  // === Session Errors ===
  SESSION_INVALID: {
    title: 'You are logged out of Twitter',
    message: 'Your Twitter session is no longer valid.',
    action: 'Log in to Twitter and click Sync again',
    level: 'BLOCKED'
  },
  
  SESSION_STALE: {
    title: 'Session needs refresh',
    message: 'Your Twitter session is outdated.',
    action: 'Re-sync your cookies to continue',
    level: 'WARNING'
  },
  
  SESSION_NOT_FOUND: {
    title: 'Session not found',
    message: 'No session exists for this account.',
    action: 'Sync cookies to create a new session',
    level: 'BLOCKED'
  },
  
  SESSION_EXPIRED: {
    title: 'Session has expired',
    message: 'Your Twitter session has timed out.',
    action: 'Log in to Twitter and sync again',
    level: 'BLOCKED'
  },
  
  // === Cookie Errors ===
  COOKIES_MISSING: {
    title: 'Required cookies missing',
    message: 'Essential Twitter cookies were not found.',
    action: 'Make sure you are logged into Twitter, then sync',
    level: 'BLOCKED'
  },
  
  COOKIES_EMPTY: {
    title: 'No cookies found',
    message: 'No Twitter cookies are available.',
    action: 'Log in to Twitter in this browser first',
    level: 'BLOCKED'
  },
  
  COOKIES_EXPIRED: {
    title: 'Cookies have expired',
    message: 'Your Twitter cookies are no longer valid.',
    action: 'Log out and log back in to Twitter',
    level: 'BLOCKED'
  },
  
  AUTH_TOKEN_MISSING: {
    title: 'Authentication missing',
    message: 'Twitter authentication cookie not found.',
    action: 'Log in to Twitter and try again',
    level: 'BLOCKED'
  },
  
  AUTH_TOKEN_EXPIRED: {
    title: 'Authentication expired',
    message: 'Your Twitter login has expired.',
    action: 'Log in to Twitter again',
    level: 'BLOCKED'
  },
  
  AUTH_TOKEN_INVALID: {
    title: 'Invalid authentication',
    message: 'Twitter did not accept your credentials.',
    action: 'Log out, clear cookies, and log in again',
    level: 'BLOCKED'
  },
  
  // === Account Errors ===
  ACCOUNT_NOT_FOUND: {
    title: 'Account not found',
    message: 'This Twitter account does not exist.',
    action: 'Check the username and try again',
    level: 'BLOCKED'
  },
  
  ACCOUNT_DISABLED: {
    title: 'Account disabled',
    message: 'This Twitter account has been disabled.',
    action: 'Contact Twitter support or use a different account',
    level: 'BLOCKED'
  },
  
  ACCOUNT_RESTRICTED: {
    title: 'Account restricted',
    message: 'Twitter has restricted this account.',
    action: 'Wait for restrictions to lift or use another account',
    level: 'BLOCKED'
  },
  
  ACCOUNT_SUSPENDED: {
    title: 'Account suspended',
    message: 'This Twitter account has been suspended.',
    action: 'Appeal to Twitter or use a different account',
    level: 'BLOCKED'
  },
  
  ACCOUNT_LOCKED: {
    title: 'Account locked',
    message: 'Twitter has locked this account for security.',
    action: 'Unlock your account on Twitter first',
    level: 'BLOCKED'
  },
  
  // === Rate Limiting ===
  RATE_LIMITED: {
    title: 'Rate limit reached',
    message: 'Twitter has temporarily limited this account.',
    action: 'Wait 15-30 minutes before trying again',
    level: 'WARNING',
    retryAfter: 30
  },
  
  RATE_LIMITED_SOFT: {
    title: 'Slow down',
    message: 'Too many requests. Please wait a moment.',
    action: 'Wait a few minutes before retrying',
    level: 'WARNING',
    retryAfter: 5
  },
  
  QUOTA_EXCEEDED: {
    title: 'Quota exceeded',
    message: 'Daily request limit has been reached.',
    action: 'Try again tomorrow',
    level: 'WARNING',
    retryAfter: 60
  },
  
  // === Service Errors ===
  PARSER_DOWN: {
    title: 'Service temporarily unavailable',
    message: 'Our parsing service is restarting.',
    action: 'Please try again in a few minutes',
    level: 'INFO'
  },
  
  PARSER_BUSY: {
    title: 'Service busy',
    message: 'The parsing service is handling other requests.',
    action: 'Please wait a moment and try again',
    level: 'WARNING',
    retryAfter: 1
  },
  
  BROWSER_NOT_READY: {
    title: 'Initializing',
    message: 'The browser engine is starting up.',
    action: 'Please wait a moment',
    level: 'INFO'
  },
  
  SERVICE_UNAVAILABLE: {
    title: 'Service unavailable',
    message: 'The service is currently down.',
    action: 'Please try again later',
    level: 'INFO'
  },
  
  // === Policy Errors ===
  POLICY_BLOCKED: {
    title: 'Action not allowed',
    message: 'This action is currently restricted.',
    action: 'Contact support if you believe this is an error',
    level: 'BLOCKED'
  },
  
  HIGH_ABORT_RATE: {
    title: 'Unstable session',
    message: 'Too many parsing failures detected.',
    action: 'Re-sync cookies or wait a few minutes',
    level: 'WARNING'
  },
  
  RISK_THRESHOLD_EXCEEDED: {
    title: 'Risk detected',
    message: 'Unusual activity detected on this account.',
    action: 'Wait a few minutes before trying again',
    level: 'WARNING'
  },
  
  COOLDOWN_ACTIVE: {
    title: 'Please wait',
    message: 'This account needs a short break.',
    action: 'Try again in 15 minutes',
    level: 'WARNING',
    retryAfter: 15
  },
  
  // === Preflight Errors ===
  PREFLIGHT_FAILED: {
    title: 'Pre-check failed',
    message: 'System requirements were not met.',
    action: 'Check your session and try again',
    level: 'BLOCKED'
  },
  
  PRECONDITION_FAILED: {
    title: 'Requirements not met',
    message: 'Some conditions for parsing were not satisfied.',
    action: 'Ensure your session is valid and sync again',
    level: 'BLOCKED'
  },
  
  // === Validation Errors ===
  INVALID_REQUEST: {
    title: 'Invalid request',
    message: 'The request could not be processed.',
    action: 'Check your input and try again',
    level: 'WARNING'
  },
  
  MISSING_PARAMETER: {
    title: 'Missing information',
    message: 'Required information was not provided.',
    action: 'Fill in all required fields',
    level: 'WARNING'
  },
  
  INVALID_PARAMETER: {
    title: 'Invalid input',
    message: 'Some input values are not valid.',
    action: 'Correct the invalid fields and retry',
    level: 'WARNING'
  },
  
  // === Generic Errors ===
  UNKNOWN_ERROR: {
    title: 'Something went wrong',
    message: 'An unexpected error occurred.',
    action: 'Please try again. If the problem persists, contact support',
    level: 'INFO'
  },
  
  INTERNAL_ERROR: {
    title: 'Internal error',
    message: 'A server error occurred.',
    action: 'Please try again later',
    level: 'INFO'
  },
  
  TIMEOUT: {
    title: 'Request timed out',
    message: 'The operation took too long.',
    action: 'Check your connection and try again',
    level: 'WARNING'
  }
};

/**
 * Get human-readable error info for an error code
 * @param {string} errorCode - Backend error code
 * @param {Object} meta - Additional metadata from backend
 * @returns {Object} Human-readable error mapping
 */
function getErrorMapping(errorCode, meta = {}) {
  const mapping = ERROR_MAP[errorCode] || ERROR_MAP.UNKNOWN_ERROR;
  
  // Customize message with metadata if available
  let customMessage = mapping.message;
  let customAction = mapping.action;
  
  if (meta.account) {
    customMessage = customMessage.replace('this account', `@${meta.account}`);
  }
  
  if (meta.retryAfter) {
    const minutes = Math.ceil(meta.retryAfter / 60);
    customAction = `Wait ${minutes} minute${minutes > 1 ? 's' : ''} before trying again`;
  }
  
  return {
    ...mapping,
    message: customMessage,
    action: customAction,
    meta
  };
}

/**
 * Get UX configuration based on error level
 * @param {'INFO' | 'WARNING' | 'BLOCKED'} level
 * @returns {Object} UI configuration
 */
function getErrorUXConfig(level) {
  switch (level) {
    case 'BLOCKED':
      return {
        icon: '❌',
        color: 'error',
        canContinue: false,
        showRetry: false
      };
    case 'WARNING':
      return {
        icon: '⚠️',
        color: 'warning',
        canContinue: true,
        showRetry: true
      };
    case 'INFO':
    default:
      return {
        icon: 'ℹ️',
        color: 'info',
        canContinue: true,
        showRetry: true
      };
  }
}

/**
 * Process backend error response into UI-ready format
 * @param {Object} errorResponse - Backend error response { ok: false, errorCode, severity, meta }
 * @returns {Object} UI-ready error object
 */
function processBackendError(errorResponse) {
  if (!errorResponse || errorResponse.ok !== false) {
    return null;
  }
  
  const { errorCode, severity, meta } = errorResponse;
  const mapping = getErrorMapping(errorCode, meta);
  const uxConfig = getErrorUXConfig(mapping.level);
  
  return {
    errorCode,
    title: mapping.title,
    message: mapping.message,
    action: mapping.action,
    retryAfter: mapping.retryAfter,
    ...uxConfig,
    meta
  };
}

// Export for use in popup.js
if (typeof window !== 'undefined') {
  window.BackendErrorMapper = {
    ERROR_MAP,
    getErrorMapping,
    getErrorUXConfig,
    processBackendError
  };
}
