/**
 * background.js — Manifest V3 service worker.
 *
 * Why this exists as a separate layer instead of having popup.js call
 * fetch() directly: keeping all backend communication in one place means
 * the backend URL, timeout logic, and error handling are defined once.
 * It also leaves room to later add automatic checks on navigation
 * (chrome.webNavigation) without touching the popup at all — the popup
 * would just become one more caller of the same message API.
 */

const BACKEND_URL = "http://127.0.0.1:5000";
const FETCH_TIMEOUT_MS = 5000;

async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...options, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(timer);
  }
}

async function checkUrl(url) {
  const res = await fetchWithTimeout(
    `${BACKEND_URL}/predict`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    },
    FETCH_TIMEOUT_MS
  );
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Backend returned ${res.status}`);
  }
  return data;
}

async function checkHealth() {
  const res = await fetchWithTimeout(`${BACKEND_URL}/health`, {}, FETCH_TIMEOUT_MS);
  if (!res.ok) throw new Error(`Backend returned ${res.status}`);
  return res.json();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "CHECK_URL") {
    checkUrl(message.url)
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true; // keep the message channel open for the async response
  }

  if (message.type === "CHECK_HEALTH") {
    checkHealth()
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: err.message }));
    return true;
  }
});
