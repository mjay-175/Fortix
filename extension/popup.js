const urlBox = document.getElementById("urlBox");
const checkBtn = document.getElementById("checkBtn");
const resultBox = document.getElementById("result");
const errorBox = document.getElementById("errorBox");
const backendStatus = document.getElementById("backendStatus");

let currentUrl = null;

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function hideError() {
  errorBox.classList.add("hidden");
}

function showResult(data) {
  resultBox.classList.remove("hidden", "legitimate", "phishing");
  resultBox.classList.add(data.prediction === "phishing" ? "phishing" : "legitimate");

  const verdictText = data.prediction === "phishing" ? "⚠ Likely phishing" : "✓ Looks legitimate";
  const sourceNote =
    data.source === "allowlist"
      ? "Matched a known trusted domain."
      : `Model confidence: ${(data.confidence * 100).toFixed(1)}%`;

  resultBox.innerHTML = `
    <div class="verdict">${verdictText}</div>
    <div class="detail">${sourceNote}</div>
    <div class="detail">Checked in ${data.inference_time_ms ?? "—"} ms</div>
  `;
}

async function loadActiveTabUrl() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) {
    urlBox.textContent = "No accessible URL for this tab.";
    checkBtn.disabled = true;
    return null;
  }
  // chrome://, about:, and the extension's own pages aren't checkable
  if (!/^https?:\/\//.test(tab.url)) {
    urlBox.textContent = tab.url;
    checkBtn.disabled = true;
    showError("This page type can't be checked (not http/https).");
    return null;
  }
  urlBox.textContent = tab.url;
  return tab.url;
}

async function checkBackendHealth() {
  chrome.runtime.sendMessage({ type: "CHECK_HEALTH" }, (response) => {
    if (response && response.ok) {
      backendStatus.textContent = "connected";
      backendStatus.className = "ok";
    } else {
      backendStatus.textContent = "not reachable";
      backendStatus.className = "down";
    }
  });
}

checkBtn.addEventListener("click", () => {
  if (!currentUrl) return;
  hideError();
  resultBox.classList.add("hidden");
  checkBtn.disabled = true;
  checkBtn.innerHTML = `<span class="spinner"></span>Checking…`;

  chrome.runtime.sendMessage({ type: "CHECK_URL", url: currentUrl }, (response) => {
    checkBtn.disabled = false;
    checkBtn.textContent = "Check this page";

    if (!response) {
      showError("No response from extension background worker.");
      return;
    }
    if (!response.ok) {
      showError(`Couldn't reach the backend: ${response.error}. Is app.py running on 127.0.0.1:5000?`);
      return;
    }
    showResult(response.data);
  });
});

(async function init() {
  currentUrl = await loadActiveTabUrl();
  checkBackendHealth();
})();
