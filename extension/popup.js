// popup.js
// ─────────────────────────────────────────────────────────────────────────────
// This is the brain of the extension popup.
// Flow:
//   1. On open → ask content.js for current URL
//   2. Ask background.js if we already have a session_id for this tab
//   3. If no session → call /scrape on the backend → store session_id
//   4. User types question → call /chat → render answer
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE = "https://webchat-api-441y.onrender.com";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const messagesEl  = document.getElementById("messages");
const inputEl     = document.getElementById("input");
const sendBtn     = document.getElementById("btn-send");
const rescanBtn   = document.getElementById("btn-rescan");
const statusBadge = document.getElementById("status-badge");
const pageTitleEl = document.getElementById("page-title");
const emptyState  = document.getElementById("empty-state");
const inputHint   = document.getElementById("input-hint");

// ── State ─────────────────────────────────────────────────────────────────────
let sessionId   = null;
let currentTabId = null;
let isLoading   = false;

// ── Init ──────────────────────────────────────────────────────────────────────
(async () => {
  // Get the active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTabId = tab.id;

  // Show URL in page bar immediately
  pageTitleEl.textContent = truncate(tab.url, 55);

  // Check if we already have a session for this tab (from background.js)
  const { sessionId: existingSession } = await chrome.runtime.sendMessage({
    type: "GET_SESSION",
    tabId: currentTabId
  });

  if (existingSession) {
    // Already scraped — ready to chat
    sessionId = existingSession;
    setStatus("ready", `ready · ${truncate(tab.title || tab.url, 38)}`);
    enableInput("page already loaded — ask away");
  } else {
    // Fresh tab — need to scrape
    await scrapeCurrentPage(tab);
  }
})();

// ── Scrape ────────────────────────────────────────────────────────────────────
async function scrapeCurrentPage(tab) {
  setStatus("loading", "loading");
  setHint("loading", "scanning page…");
  rescanBtn.classList.add("spinning");
  sendBtn.disabled = true;

  try {
    // Ask content.js for the exact URL (handles redirects correctly)
    let url = tab.url;
    try {
      const resp = await chrome.tabs.sendMessage(currentTabId, { type: "GET_URL" });
      if (resp?.url) url = resp.url;
    } catch (_) {
      // content script not injected yet on some pages — fall back to tab.url
    }

    pageTitleEl.textContent = truncate(url, 55);

    const res = await fetch(`${API_BASE}/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    sessionId = data.session_id;

    // Store session in background.js so it persists across popup open/close
    await chrome.runtime.sendMessage({
      type: "SET_SESSION",
      tabId: currentTabId,
      sessionId
    });

    pageTitleEl.textContent = truncate(data.page_title, 55);
    setStatus("ready", "ready");
    enableInput(`${data.chunks_stored} chunks indexed — ask away`);

  } catch (err) {
    setStatus("error", "error");
    setHint("error", `failed: ${err.message}`);
    appendMessage("error", `Could not load this page: ${err.message}. Try the rescan button, or check if the page is publicly accessible.`);
  } finally {
    rescanBtn.classList.remove("spinning");
  }
}

// ── Chat ──────────────────────────────────────────────────────────────────────
async function sendQuestion() {
  const question = inputEl.value.trim();
  if (!question || !sessionId || isLoading) return;

  isLoading = true;
  inputEl.value = "";
  autoResize();
  sendBtn.disabled = true;
  setStatus("thinking", "thinking");

  // Hide empty state
  if (emptyState) emptyState.style.display = "none";

  // Render user message
  appendMessage("user", question);

  // Render typing indicator
  const typingEl = appendTyping();

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, question })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server error ${res.status}`);
    }

    const data = await res.json();
    typingEl.remove();
    appendMessage("ai", data.answer);

  } catch (err) {
    typingEl.remove();
    appendMessage("error", `Something went wrong: ${err.message}`);
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
    setStatus("ready", "ready");
    inputEl.focus();
  }
}

// ── Rescan button ─────────────────────────────────────────────────────────────
rescanBtn.addEventListener("click", async () => {
  if (isLoading) return;

  // Clear existing session
  await chrome.runtime.sendMessage({ type: "CLEAR_SESSION", tabId: currentTabId });
  sessionId = null;
  sendBtn.disabled = true;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  await scrapeCurrentPage(tab);
});

// ── Input handling ────────────────────────────────────────────────────────────
inputEl.addEventListener("input", () => {
  autoResize();
  sendBtn.disabled = !inputEl.value.trim() || !sessionId || isLoading;
});

inputEl.addEventListener("keydown", (e) => {
  // Send on Enter, new line on Shift+Enter
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendQuestion();
  }
});

sendBtn.addEventListener("click", sendQuestion);

function autoResize() {
  inputEl.style.height = "auto";
  inputEl.style.height = Math.min(inputEl.scrollHeight, 90) + "px";
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function appendMessage(role, text) {
  const msg = document.createElement("div");
  msg.className = `msg ${role}`;

  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = role === "user" ? "you" : role === "ai" ? "webchat" : "error";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;

  msg.appendChild(label);
  msg.appendChild(bubble);
  messagesEl.appendChild(msg);
  scrollToBottom();
  return msg;
}

function appendTyping() {
  const msg = document.createElement("div");
  msg.className = "msg ai";

  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = "webchat";

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.innerHTML = `
    <div class="typing-dots">
      <span></span><span></span><span></span>
    </div>`;

  msg.appendChild(label);
  msg.appendChild(bubble);
  messagesEl.appendChild(msg);
  scrollToBottom();
  return msg;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setStatus(type, text) {
  statusBadge.className = `badge badge-${type}`;
  statusBadge.textContent = text;
}

function setHint(type, text) {
  inputHint.className = `input-hint ${type}`;
  inputHint.textContent = text;
}

function enableInput(hint) {
  sendBtn.disabled = true; // still disabled until user types
  inputEl.disabled = false;
  setHint("ready", hint);
  inputEl.focus();
}

function truncate(str, max) {
  if (!str) return "";
  return str.length > max ? str.slice(0, max) + "…" : str;
}
