/**
 * Faculty Intelligence — Popup Logic v3
 * ======================================
 * Single Profile mode  — classify the current tab directly via /classify
 * Directory Scrape mode — delegates to background.js service worker via
 *                         chrome.runtime.connect so scraping survives popup close.
 *
 * On popup open, checks chrome.storage.local for a running or recently
 * completed scrape and restores the progress UI.
 */

const SERVER = "http://localhost:8765";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const statusDot     = document.getElementById("statusDot");
const statusText    = document.getElementById("statusText");
const statCount     = document.getElementById("statCount");
const currentUrl    = document.getElementById("currentUrl");
const exportBtn     = document.getElementById("exportBtn");
const exportLabel   = document.getElementById("exportLabel");
const toast         = document.getElementById("toast");

// Single mode
const scrapeBtn     = document.getElementById("scrapeBtn");
const scrapeIcon    = document.getElementById("scrapeIcon");
const scrapeBtnText = document.getElementById("scrapeBtnText");
const errorBanner   = document.getElementById("errorBanner");
const resultCard    = document.getElementById("resultCard");
const resultTitle   = document.getElementById("resultTitle");
const resultBadge   = document.getElementById("resultBadge");
const resultBody    = document.getElementById("resultBody");

// API Key Card refs
const apiKeyCard          = document.getElementById("apiKeyCard");
const apiKeyHeader        = document.getElementById("apiKeyHeader");
const apiKeyBadge         = document.getElementById("apiKeyBadge");
const apiKeyChevron       = document.getElementById("apiKeyChevron");
const apiKeyBody          = document.getElementById("apiKeyBody");
const groqApiKeyInput     = document.getElementById("groqApiKeyInput");
const toggleKeyVisibility = document.getElementById("toggleKeyVisibility");
const saveApiKeyBtn       = document.getElementById("saveApiKeyBtn");

// Directory mode
const dirScrapeBtn     = document.getElementById("dirScrapeBtn");
const dirScrapeIcon    = document.getElementById("dirScrapeIcon");
const dirScrapeBtnText = document.getElementById("dirScrapeBtnText");
const dirStopBtn       = document.getElementById("dirStopBtn");
const dirErrorBanner   = document.getElementById("dirErrorBanner");
const progressPanel    = document.getElementById("progressPanel");
const progressTitle    = document.getElementById("progressTitle");
const pSaved           = document.getElementById("pSaved");
const pProcessed       = document.getElementById("pProcessed");
const pTotal           = document.getElementById("pTotal");
const progressBar      = document.getElementById("progressBar");
const progressPct      = document.getElementById("progressPct");
const liveFeed         = document.getElementById("liveFeed");
const cfgMaxPages      = document.getElementById("cfgMaxPages");
const cfgMaxProfiles   = document.getElementById("cfgMaxProfiles");

// ── State ─────────────────────────────────────────────────────────────────────
let serverOnline  = false;
let currentTabUrl = "";
let bgPort        = null;   // Port to background service worker

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  await initApiKey();
  await Promise.all([checkServerStatus(), loadCurrentTab()]);
  await restoreProgressFromStorage(); // Show any ongoing/completed scrape
})();

// ── API Key Management ────────────────────────────────────────────────────────
async function initApiKey() {
  // Header collapse toggle
  apiKeyHeader.addEventListener("click", () => {
    const isHidden = apiKeyBody.classList.toggle("hidden");
    apiKeyChevron.classList.toggle("open", !isHidden);
  });

  // Password visibility toggle
  toggleKeyVisibility.addEventListener("click", (e) => {
    e.stopPropagation();
    groqApiKeyInput.type = groqApiKeyInput.type === "password" ? "text" : "password";
  });

  // Save Key handler
  saveApiKeyBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    const keyVal = groqApiKeyInput.value.trim();
    if (!keyVal) {
      showToast("Please paste a valid Groq API key", "error");
      return;
    }
    await saveApiKey(keyVal);
  });

  // Load key from storage
  const stored = await chrome.storage.local.get("groqApiKey");
  if (stored.groqApiKey) {
    groqApiKeyInput.value = stored.groqApiKey;
    await sendApiKeyToServer(stored.groqApiKey, false);
  }
}

async function saveApiKey(keyVal) {
  saveApiKeyBtn.disabled = true;
  saveApiKeyBtn.textContent = "Saving…";
  try {
    await chrome.storage.local.set({ groqApiKey: keyVal });
    const ok = await sendApiKeyToServer(keyVal, true);
    if (ok) {
      setTimeout(() => {
        apiKeyBody.classList.add("hidden");
        apiKeyChevron.classList.remove("open");
      }, 1500);
    }
  } finally {
    saveApiKeyBtn.disabled = false;
    saveApiKeyBtn.textContent = "Save Key";
  }
}

async function sendApiKeyToServer(keyVal, showToastOnSuccess = true) {
  try {
    const resp = await fetch(`${SERVER}/set-api-key`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ groq_api_key: keyVal }),
    });
    if (resp.ok) {
      const data = await resp.json();
      updateApiKeyStatusUI(true, data.api_key_masked);
      hideError();
      if (serverOnline) {
        scrapeBtn.disabled    = false;
        dirScrapeBtn.disabled = false;
      }
      if (showToastOnSuccess) showToast("✓ Groq API Key updated!", "success");
      return true;
    } else {
      const err = await resp.json().catch(() => ({ detail: "Failed to update key" }));
      if (showToastOnSuccess) showToast(`Key error: ${err.detail}`, "error");
      return false;
    }
  } catch {
    return false;
  }
}

function updateApiKeyStatusUI(keySet, maskedKey) {
  if (keySet) {
    apiKeyBadge.className = "api-key-badge set";
    apiKeyBadge.textContent = maskedKey ? `✓ ${maskedKey}` : "✓ Key Set";
    apiKeyCard.classList.remove("warning");
  } else {
    apiKeyBadge.className = "api-key-badge unset";
    apiKeyBadge.textContent = "⚠ Key Required";
    apiKeyCard.classList.add("warning");
    apiKeyBody.classList.remove("hidden");
    apiKeyChevron.classList.add("open");
  }
}

// ── Mode switching ────────────────────────────────────────────────────────────
function switchMode(mode) {
  document.getElementById("tabSingle").classList.toggle("active",    mode === "single");
  document.getElementById("tabDirectory").classList.toggle("active", mode === "directory");
  document.getElementById("modeSingle").classList.toggle("hidden",    mode !== "single");
  document.getElementById("modeDirectory").classList.toggle("hidden", mode !== "directory");
}

// ── Server health ─────────────────────────────────────────────────────────────
async function checkServerStatus() {
  try {
    const resp = await fetch(`${SERVER}/status`, { signal: AbortSignal.timeout(3000) });
    if (resp.ok) {
      const data = await resp.json();
      serverOnline = true;
      statusDot.className    = "status-dot online";
      statusText.textContent = "Connected";
      statCount.textContent  = data.record_count ?? "0";

      updateApiKeyStatusUI(data.api_key_set, data.api_key_masked);

      if (!data.api_key_set) {
        showError("⚠ GROQ_API_KEY required. Paste your Groq API key above.");
        scrapeBtn.disabled    = true;
        dirScrapeBtn.disabled = true;
      } else {
        hideError();
        scrapeBtn.disabled    = false;
        dirScrapeBtn.disabled = false;
      }
    } else { throw new Error(); }
  } catch {
    serverOnline = false;
    statusDot.className    = "status-dot offline";
    statusText.textContent = "Offline";
    statCount.textContent  = "—";
    showError("🔌 Server offline.\n\nRun: python server.py");
    scrapeBtn.disabled    = true;
    dirScrapeBtn.disabled = true;
  }
}

async function loadCurrentTab() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url) { currentTabUrl = tab.url; currentUrl.textContent = tab.url; currentUrl.title = tab.url; }
  } catch { currentUrl.textContent = "Unable to read current tab"; }
}

// ── Restore progress UI from storage (popup reopen) ──────────────────────────
async function restoreProgressFromStorage() {
  const result = await chrome.storage.local.get("scrapeState");
  const state  = result.scrapeState;
  if (!state) return;

  // Only restore if recent (within last 2 hours)
  if (Date.now() - (state.startedAt || 0) > 2 * 60 * 60 * 1000) return;

  // Switch to directory tab and show progress
  switchMode("directory");
  progressPanel.classList.remove("hidden");

  pSaved.textContent     = state.saved     || "0";
  pProcessed.textContent = state.processed || "0";
  pTotal.textContent     = state.total     || "?";

  const pct = state.total > 0 ? Math.round((state.processed / state.total) * 100) : 0;
  progressBar.style.width = `${pct}%`;
  progressPct.textContent  = `${pct}%`;

  if (state.status === "running") {
    progressTitle.textContent = "⚡ Scraping in background…";
    setDirLoading(true);
    // Re-attach to background worker to receive live events
    connectToBackground();
  } else if (state.status === "done") {
    progressTitle.textContent = "✅ Complete";
  } else if (state.status === "stopped") {
    progressTitle.textContent = "⏹ Stopped";
  } else if (state.status === "error") {
    progressTitle.textContent = "❌ Error";
    showDirError(state.error || "Unknown error");
  }

  // Render stored feed (most recent first — already ordered)
  liveFeed.innerHTML = "";
  for (const item of (state.feed || []).slice(0, 50)) {
    addFeedItemRaw(item.type, item.text, false);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  SINGLE PROFILE MODE
// ═══════════════════════════════════════════════════════════════════════════════
scrapeBtn.addEventListener("click", async () => {
  if (!serverOnline) { showError("Server offline. Run: python server.py"); return; }
  hideError(); hideResult(); setLoading(true);

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    let pageHtml = "", pageUrl = tab.url || "";

    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => ({ html: document.documentElement.outerHTML, url: window.location.href }),
      });
      if (results?.[0]?.result) { pageHtml = results[0].result.html; pageUrl = results[0].result.url; }
    } catch (e) { throw new Error(`Cannot access page: ${e.message}. Try refreshing.`); }

    if (!pageHtml) throw new Error("Got empty HTML. Try refreshing the page.");
    if (pageHtml.length > 2_000_000) pageHtml = pageHtml.slice(0, 2_000_000);

    const stored = await chrome.storage.local.get("groqApiKey");
    const payload = { html: pageHtml, url: pageUrl };
    if (stored.groqApiKey) payload.groq_api_key = stored.groqApiKey;

    const resp = await fetch(`${SERVER}/classify`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(60_000),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || `Server error ${resp.status}`);
    }

    const result = await resp.json();
    refreshCount();
    renderResult(result);

  } catch (e) {
    showError(`❌ ${e.message}`);
  } finally {
    setLoading(false);
  }
});

function renderResult(result) {
  resultCard.classList.remove("hidden");

  if (!result.is_south_asian) {
    resultTitle.textContent = "Classification Result";
    resultBadge.className   = "badge badge-excluded";
    resultBadge.textContent = "Excluded";
    resultBody.innerHTML = `
      <div class="exclusion-reason">
        <strong>Not South Asian</strong><br/>
        ${escHtml(result.reason || "Name does not match South Asian name database.")}
        ${result.name ? `<br/><br/>Detected name: <strong>${escHtml(result.name)}</strong>` : ""}
      </div>`;
    return;
  }

  if (!result.is_valid_role) {
    resultTitle.textContent = "Classification Result";
    resultBadge.className   = "badge badge-partial";
    resultBadge.textContent = "Not Faculty";
    resultBody.innerHTML = `
      <div style="margin-bottom:8px;">
        <div class="profile-name">${escHtml(result.name || "Unknown")}</div>
        <div class="profile-role">${escHtml(result.role || "—")}</div>
      </div>
      <div class="partial-reason">
        ⚠ South Asian name, but role is not a qualifying faculty position.<br/>
        ${escHtml(result.reason || "")}
      </div>`;
    return;
  }

  resultTitle.textContent = "Faculty Profile";
  resultBadge.className   = "badge badge-included";
  resultBadge.textContent = "✓ Included";

  resultBody.innerHTML = `
    <div class="profile-name">${escHtml(result.name)}</div>
    <div class="profile-role">${escHtml(result.role)}</div>
    <div class="info-grid">
      <div class="info-item">
        <div class="info-label">Origin</div>
        <div class="info-value highlight">${escHtml(result.origin || "—")}</div>
      </div>
      <div class="info-item">
        <div class="info-label">Email</div>
        <div class="info-value">${escHtml(result.email || "—")}</div>
      </div>
      <div class="info-item" style="grid-column:1/-1">
        <div class="info-label">University</div>
        <div class="info-value">${escHtml(result.university || "—")}</div>
      </div>
      <div class="info-item" style="grid-column:1/-1">
        <div class="info-label">Department</div>
        <div class="info-value">${escHtml(result.department || "—")}</div>
      </div>
    </div>
    <div class="info-full">
      <div class="info-label">Research Interests</div>
      <div class="info-value">${escHtml(result.research_interests || "—")}</div>
    </div>
    <div class="info-full">
      <div class="info-label">Summary</div>
      <div class="info-value">${escHtml(result.summary || "—")}</div>
    </div>
    <div class="action-row">
      <button class="btn-secondary" id="openProfileBtn">🔗 Open Profile</button>
      <button class="btn-save" id="saveBtn">💾 Save to Dataset</button>
    </div>`;

  document.getElementById("openProfileBtn").addEventListener("click", () => chrome.tabs.create({ url: result.profile_link }));
  document.getElementById("saveBtn").addEventListener("click", () => saveRecord(result));
}

async function saveRecord(record) {
  const btn = document.getElementById("saveBtn");
  if (!btn) return;
  btn.disabled = true; btn.textContent = "Saving…";
  try {
    const resp = await fetch(`${SERVER}/save`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ record }),
    });
    const data = await resp.json();
    if (data.status === "saved") {
      statCount.textContent = data.total;
      btn.textContent = "✓ Saved!";
      showToast(`✓ ${record.name} saved`, "success");
    } else {
      btn.textContent = "Already saved";
      showToast("Already in dataset", "error");
    }
  } catch (e) {
    btn.disabled = false; btn.textContent = "💾 Save to Dataset";
    showToast(`Save failed: ${e.message}`, "error");
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  DIRECTORY SCRAPE MODE — delegates to background service worker
// ═══════════════════════════════════════════════════════════════════════════════
dirScrapeBtn.addEventListener("click", () => {
  if (!serverOnline) { showDirError("Server offline. Run: python server.py"); return; }
  startDirectoryScrape();
});

dirStopBtn.addEventListener("click", () => {
  if (bgPort) {
    bgPort.postMessage({ action: "stop" });
  }
});

function connectToBackground() {
  try {
    bgPort = chrome.runtime.connect({ name: "facultyScrape" });

    bgPort.onMessage.addListener(event => {
      if (event.type === "state") {
        // Initial state sync after reconnect — handled by restoreProgressFromStorage
        return;
      }
      handleSSEEvent(event);
    });

    bgPort.onDisconnect.addListener(() => {
      bgPort = null;
      // SW was killed (rare) — update UI
      if (progressTitle.textContent.includes("background")) {
        progressTitle.textContent = "⚠ Worker disconnected";
      }
    });

    return bgPort;
  } catch (e) {
    showDirError(`Cannot connect to background worker: ${e.message}`);
    return null;
  }
}

async function startDirectoryScrape() {
  hideDirError();
  setDirLoading(true);
  resetProgress();

  const config = {
    url:          currentTabUrl,
    max_pages:    parseInt(cfgMaxPages.value)    || 100,
    max_profiles: parseInt(cfgMaxProfiles.value) || 1000,
  };

  const port = connectToBackground();
  if (!port) { setDirLoading(false); return; }

  port.postMessage({ action: "start", config });
  progressPanel.classList.remove("hidden");
  addFeedItemRaw("page", `🔍 Sent to background worker — you can close this popup and reopen it to check progress.`);
}

// ── SSE event handler (receives events from background.js) ────────────────────
function handleSSEEvent(ev) {
  switch (ev.type) {

    case "start":
      progressTitle.textContent = "Discovering profiles…";
      addFeedItemRaw("page", `🔍 Starting: ${shortenUrl(ev.url)}`);
      break;

    case "page":
      addFeedItemRaw("page", `📄 Page ${ev.page}: ${ev.profiles_found} profile link(s) — total ${ev.total_profiles}`);
      pTotal.textContent = ev.total_profiles;
      progressTitle.textContent = `Discovering… (page ${ev.page})`;
      break;

    case "progress": {
      const idx   = ev.index || 0;
      const total = ev.total || 0;
      const pct   = total > 0 ? Math.round((idx / total) * 100) : 0;
      progressBar.style.width = `${pct}%`;
      progressPct.textContent  = `${pct}%`;
      pProcessed.textContent   = idx;
      pTotal.textContent       = total;
      progressTitle.textContent = `Classifying ${idx} / ${total}…`;

      let label;
      if (ev.status === "included")   label = `<span class="included-name">✓ ${escHtml(ev.name)}</span>`;
      else if (ev.status === "not_faculty") label = `⚠ ${escHtml(ev.name)} (not faculty)`;
      else if (ev.status === "duplicate")   label = `↩ Skipped (duplicate)`;
      else if (ev.status === "excluded")    label = `✗ ${escHtml(ev.name || shortenUrl(ev.url))} (not South Asian)`;
      else                                  label = `✗ ${shortenUrl(ev.url)} (${ev.status})`;
      addFeedItemRaw(ev.status || "excluded", label, false);
      break;
    }

    case "saved":
      pSaved.textContent = ev.total_saved;
      refreshCount();
      break;

    case "done":
      progressBar.style.width = "100%";
      progressPct.textContent  = "100%";
      pProcessed.textContent   = ev.profiles_found;
      pTotal.textContent       = ev.profiles_found;
      progressTitle.textContent = "✅ Complete";
      addFeedItemRaw("done", `✅ Done — ${ev.saved} saved · ${ev.pages_crawled} pages · ${ev.profiles_found} profiles`);
      showToast(`✅ ${ev.saved} faculty saved from ${ev.pages_crawled} pages`, "success");
      refreshCount();
      setDirLoading(false);
      break;

    case "stopped":
      progressTitle.textContent = "⏹ Stopped";
      addFeedItemRaw("stop", "⏹ Scrape stopped by user.");
      setDirLoading(false);
      break;

    case "error":
      addFeedItemRaw("error", `❌ ${ev.message}`);
      showDirError(ev.message);
      setDirLoading(false);
      break;
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
//  EXPORT
// ═══════════════════════════════════════════════════════════════════════════════
exportBtn.addEventListener("click", async () => {
  exportBtn.disabled = true;
  exportBtn.textContent = "⏳ Exporting…";
  try {
    const resp = await fetch(`${SERVER}/export`);
    const data = await resp.json();
    if (data.status === "exported") {
      showToast("✓ Exported! Check output/ folder", "success");
      exportLabel.textContent = `Last export: ${new Date().toLocaleTimeString()}`;
    }
  } catch (e) {
    showToast(`Export failed: ${e.message}`, "error");
  } finally {
    exportBtn.disabled = false;
    exportBtn.textContent = "📊 Export";
  }
});

// ═══════════════════════════════════════════════════════════════════════════════
//  UI HELPERS
// ═══════════════════════════════════════════════════════════════════════════════
function setLoading(on) {
  scrapeBtn.disabled = on;
  scrapeIcon.innerHTML   = on ? '<span class="spinner"></span>' : "⚡";
  scrapeBtnText.textContent = on ? "Classifying…" : "Classify This Page";
}

function setDirLoading(on) {
  dirScrapeBtn.classList.toggle("hidden", on);
  dirStopBtn.classList.toggle("hidden", !on);
  cfgMaxPages.disabled    = on;
  cfgMaxProfiles.disabled = on;
}

function resetProgress() {
  progressPanel.classList.add("hidden");
  liveFeed.innerHTML = "";
  pSaved.textContent = "0"; pProcessed.textContent = "0"; pTotal.textContent = "?";
  progressBar.style.width = "0%"; progressPct.textContent = "0%";
  progressTitle.textContent = "Starting…";
}

function addFeedItemRaw(status, html, scrollToBottom = true) {
  const item = document.createElement("div");
  item.className = "feed-item";
  item.innerHTML = `<div class="feed-dot ${status}"></div><div class="feed-text">${html}</div>`;
  liveFeed.appendChild(item);
  if (scrollToBottom) liveFeed.scrollTop = liveFeed.scrollHeight;
}

function showError(msg)    { errorBanner.textContent = msg;    errorBanner.classList.remove("hidden"); }
function hideError()       { errorBanner.classList.add("hidden"); }
function hideResult()      { resultCard.classList.add("hidden"); }
function showDirError(msg) { dirErrorBanner.textContent = msg; dirErrorBanner.classList.remove("hidden"); }
function hideDirError()    { dirErrorBanner.classList.add("hidden"); }

function showToast(msg, type = "") {
  toast.textContent = msg; toast.className = `toast ${type} show`;
  setTimeout(() => toast.classList.remove("show"), 3000);
}

async function refreshCount() {
  try {
    const d = await fetch(`${SERVER}/status`).then(r => r.json());
    statCount.textContent = d.record_count ?? "?";
  } catch {}
}

function escHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function shortenUrl(url) {
  try { return new URL(url).pathname.split("/").filter(Boolean).slice(-2).join("/"); }
  catch { return url; }
}
