const API_URL = process.env.REACT_APP_BACKEND_URL;

export async function apiRequest(url, options = {}) {
  const { method = 'GET', body, headers = {}, signal, timeout = 15000 } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${API_URL}${url}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: signal || controller.signal
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API ${res.status}: ${text}`);
    }

    return res.json();
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}

// Simple cache
const cache = new Map();
const CACHE_TTL = 30000; // 30 seconds

export async function apiGet(url, options = {}) {
  const { useCache = false, cacheTTL = CACHE_TTL } = options;
  
  if (useCache && cache.has(url)) {
    const { data, timestamp } = cache.get(url);
    if (Date.now() - timestamp < cacheTTL) {
      return data;
    }
    cache.delete(url);
  }

  const data = await apiRequest(url, { method: 'GET', ...options });
  
  if (useCache) {
    cache.set(url, { data, timestamp: Date.now() });
  }
  
  return data;
}

export async function apiPost(url, body, options = {}) {
  return apiRequest(url, { method: 'POST', body, ...options });
}

export async function apiPut(url, body, options = {}) {
  return apiRequest(url, { method: 'PUT', body, ...options });
}

export async function apiDelete(url, options = {}) {
  return apiRequest(url, { method: 'DELETE', ...options });
}

// Retry wrapper
export async function withRetry(fn, retries = 2, delay = 1000) {
  try {
    return await fn();
  } catch (e) {
    if (retries === 0) throw e;
    await new Promise(r => setTimeout(r, delay));
    return withRetry(fn, retries - 1, delay * 2);
  }
}

export function clearCache() {
  cache.clear();
}

