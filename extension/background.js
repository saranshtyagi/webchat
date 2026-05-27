// Listen for tab navigation — clear the session when the user goes to a new URL
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && changeInfo.url) {
    // User navigated to a new page — old session is stale, clear it
    chrome.storage.session.remove(`session_${tabId}`);
  }
});

// Clear session when a tab is closed
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.session.remove(`session_${tabId}`);
});

// Handle messages from popup.js
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

  if (message.type === "GET_SESSION") {
    // Popup asking: do we already have a session_id for this tab?
    chrome.storage.session.get(`session_${message.tabId}`, (result) => {
      sendResponse({ sessionId: result[`session_${message.tabId}`] || null });
    });
    return true; // async
  }

  if (message.type === "SET_SESSION") {
    // Popup telling us: store this session_id for this tab
    chrome.storage.session.set({ [`session_${message.tabId}`]: message.sessionId });
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === "CLEAR_SESSION") {
    chrome.storage.session.remove(`session_${message.tabId}`);
    sendResponse({ ok: true });
    return true;
  }
});
