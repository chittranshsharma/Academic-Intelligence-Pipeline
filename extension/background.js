/**
 * Faculty Intelligence — Background Service Worker
 * =================================================
 * Runs the directory scrape SSE stream independently of the popup.
 * Survives popup close. Saves all progress to chrome.storage.local
 * so the popup can re-open and see what's happened.
 *
 * Message protocol (popup → SW via chrome.runtime.connect "facultyScrape"):
 *   { action: "start",     config: { url, max_pages, max_profiles } }
 *   { action: "stop" }
 *   { action: "getState" }
 *
 * Message protocol (SW → popup):
 *   Any SSE event object from the server (type: start/page/progress/saved/done/error)
 *   { type: "stopped" }
 */

const SERVER = "http://localhost:8765";

// ── State ─────────────────────────────────────────────────────────────────────
let activeScrapeAbort = null;   // AbortController for the fetch stream
let activePort        = null;   // MessageChannel to popup (null when popup closed)

// ── Keep-alive alarm ──────────────────────────────────────────────────────────
// MV3 service workers are killed after ~30s of inactivity.
// We fire an alarm every 20s during an active scrape to keep the SW alive.
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "keepAlive") {
    // Receiving the alarm is enough to keep the SW running.
    // Also check if scrape is still running; if not, clear the alarm.
    if (!activeScrapeAbort) {
      chrome.alarms.clear("keepAlive");
    }
  }
});

function startKeepAlive() {
  chrome.alarms.create("keepAlive", { periodInMinutes: 0.33 }); // every ~20s
}

function stopKeepAlive() {
  chrome.alarms.clear("keepAlive");
}

// ── Port connection from popup ────────────────────────────────────────────────
chrome.runtime.onConnect.addListener(port => {
  if (port.name !== "facultyScrape") return;

  activePort = port;

  port.onMessage.addListener(async msg => {
    switch (msg.action) {
      case "start":
        await runDirectoryScrape(msg.config, port);
        break;

      case "stop":
        if (activeScrapeAbort) {
          activeScrapeAbort.abort();
          activeScrapeAbort = null;
        }
        stopKeepAlive();
        await patchState({ status: "stopped" });
        safeSend(port, { type: "stopped" });
        break;

      case "getState": {
        const state = await loadState();
        safeSend(port, { type: "state", state });
        break;
      }
    }
  });

  port.onDisconnect.addListener(() => {
    // Popup closed — scrape keeps running, we just can't push events.
    // Everything is written to chrome.storage.local so popup can re-read on reopen.
    activePort = null;
  });
});

// ── Core scrape logic ─────────────────────────────────────────────────────────
async function runDirectoryScrape(config, port) {
  // Don't start a second scrape if one is already running
  if (activeScrapeAbort) {
    safeSend(port, { type: "error", message: "A scrape is already running." });
    return;
  }

  activeScrapeAbort = new AbortController();
  startKeepAlive();

  // Reset storage state
  await saveState({
    status:    "running",
    url:       config.url,
    saved:     0,
    processed: 0,
    total:     0,
    pages:     0,
    feed:      [],
    startedAt: Date.now(),
  });

  // Attach stored Groq API Key if present
  const stored = await chrome.storage.local.get("groqApiKey");
  if (stored.groqApiKey) {
    config.groq_api_key = stored.groqApiKey;
  }

  try {
    const resp = await fetch(`${SERVER}/scrape-directory`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(config),
      signal:  activeScrapeAbort.signal,
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    // Read SSE stream line by line
    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop(); // Hold the incomplete last line

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const jsonStr = trimmed.slice(5).trim();
        if (!jsonStr) continue;

        let event;
        try { event = JSON.parse(jsonStr); } catch { continue; }

        // Forward to popup if it's still open
        safeSend(port, event);

        // Persist progress to storage (popup can read this on reopen)
        await applyEventToState(event);
      }
    }

  } catch (e) {
    if (e.name === "AbortError") {
      // User stopped — already handled above
    } else {
      const errEvent = { type: "error", message: e.message };
      safeSend(port, errEvent);
      await patchState({ status: "error", error: e.message });
    }
  } finally {
    activeScrapeAbort = null;
    stopKeepAlive();
  }
}

// ── Storage helpers ───────────────────────────────────────────────────────────
async function loadState() {
  const result = await chrome.storage.local.get("scrapeState");
  return result.scrapeState || null;
}

async function saveState(state) {
  await chrome.storage.local.set({ scrapeState: state });
}

async function patchState(patch) {
  const current = await loadState() || {};
  await saveState({ ...current, ...patch });
}

async function applyEventToState(event) {
  const state = await loadState() || {};
  const feed  = state.feed || [];

  switch (event.type) {
    case "start":
      feed.unshift({ type: "page", text: `🔍 Starting: ${event.url}` });
      break;

    case "page":
      state.pages = event.page;
      state.total = event.total_profiles;
      feed.unshift({ type: "page", text: `📄 Page ${event.page}: ${event.profiles_found} link(s) — total ${event.total_profiles}` });
      break;

    case "progress":
      state.processed = event.index;
      state.total     = event.total || state.total;
      if (event.status === "included" && event.name) {
        feed.unshift({ type: "included", text: `✓ ${event.name}` });
      }
      break;

    case "saved":
      state.saved = event.total_saved;
      break;

    case "done":
      state.status    = "done";
      state.saved     = event.saved;
      state.processed = event.profiles_found;
      state.pages     = event.pages_crawled;
      feed.unshift({ type: "done", text: `✅ Done — ${event.saved} saved · ${event.pages_crawled} pages · ${event.profiles_found} profiles` });
      break;

    case "error":
      state.status = "error";
      state.error  = event.message;
      feed.unshift({ type: "error", text: `❌ ${event.message}` });
      break;
  }

  state.feed = feed.slice(0, 200); // keep last 200 feed items
  await saveState(state);
}

// ── Utility ───────────────────────────────────────────────────────────────────
function safeSend(port, msg) {
  try { port.postMessage(msg); } catch { /* popup closed, silently ignore */ }
}
