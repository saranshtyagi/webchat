chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "GET_URL") {
    sendResponse({ url: window.location.href });
  }
  // Return true to keep the message channel open for async sendResponse
  return true;
});