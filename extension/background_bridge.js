// Chrome-native bridge policy, kept pure enough to test under node:
// prefer the installed Mac app; use the extension's older OAuth token only
// when Chrome cannot launch the native host. A real 401/403/429 from the app
// is authoritative and must never be hidden by a second credential path.

const ICARUS_NATIVE_HOST = "com.icarus.extension";

function sendNativeMessage(message, chromeApi = chrome) {
  return new Promise((resolve, reject) => {
    try {
      chromeApi.runtime.sendNativeMessage(ICARUS_NATIVE_HOST, message, (response) => {
        const error = chromeApi.runtime.lastError;
        if (error) {
          reject(new Error(error.message || "Icarus Mac bridge unavailable"));
          return;
        }
        resolve(response);
      });
    } catch (error) {
      reject(error);
    }
  });
}

async function bridgeFirst(message, fallback, send = sendNativeMessage) {
  let response;
  try {
    response = await send(message);
  } catch (error) {
    const detail = error && typeof error.message === "string"
      ? error.message
      : "Icarus Mac bridge failed";
    if (/specified native messaging host not found/i.test(detail)) {
      return fallback();
    }
    return {
      ok: false,
      status: 502,
      error: detail,
    };
  }
  if (!response || typeof response.ok !== "boolean") {
    return {
      ok: false,
      status: 502,
      error: "Icarus Mac bridge returned an invalid response",
    };
  }
  return response;
}

function validateStatusResponse(data) {
  return !!data
    && typeof data.repo === "string"
    && data.repo.length > 0
    && typeof data.state === "string"
    && data.state.length > 0;
}

function validateExplainResponse(data) {
  if (!data || !["answer", "unknown"].includes(data.verdict)
      || typeof data.answer !== "string"
      || !Array.isArray(data.citations)
      || !Array.isArray(data.searched)) {
    return false;
  }
  if (!data.citations.every((citation) => citation
      && typeof citation.ref === "string" && citation.ref.length > 0)) {
    return false;
  }
  return data.verdict !== "answer" || data.citations.length > 0;
}

globalThis.IcarusBridge = {
  hostName: ICARUS_NATIVE_HOST,
  sendNativeMessage,
  bridgeFirst,
  validateStatusResponse,
  validateExplainResponse,
};

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    ICARUS_NATIVE_HOST,
    sendNativeMessage,
    bridgeFirst,
    validateStatusResponse,
    validateExplainResponse,
  };
}
