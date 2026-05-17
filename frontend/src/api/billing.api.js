/**
 * Billing API client.
 */
const API = process.env.REACT_APP_BACKEND_URL;

export async function createCheckout(interval = 'month', promoCode = '') {
  const body = { origin_url: window.location.origin, interval };
  if (promoCode) body.promo_code = promoCode;
  const res = await fetch(`${API}/api/billing/create-checkout`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function createCryptoCheckout(interval = 'month') {
  const res = await fetch(`${API}/api/billing/create-crypto-checkout`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin_url: window.location.origin, interval }),
  });
  return res.json();
}

export async function getPlans() {
  try {
    const res = await fetch(`${API}/api/billing/plans`);
    if (!res.ok) return { ok: false };
    const data = await res.json();
    return data;
  } catch (e) {
    console.error('getPlans error:', e);
    return { ok: false };
  }
}

export async function getBillingStatus() {
  const res = await fetch(`${API}/api/billing/status`, { credentials: 'include' });
  return res.json();
}

export async function openPortal() {
  const res = await fetch(`${API}/api/billing/portal`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origin_url: window.location.origin }),
  });
  return res.json();
}

export async function checkCheckoutStatus(sessionId) {
  const res = await fetch(`${API}/api/billing/checkout-status/${sessionId}`, {
    credentials: 'include',
  });
  return res.json();
}

export async function checkCryptoCheckoutStatus(sessionId) {
  const res = await fetch(`${API}/api/billing/crypto-checkout-status/${sessionId}`, {
    credentials: 'include',
  });
  return res.json();
}
