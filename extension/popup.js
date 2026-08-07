// extension/popup.js
// Minimal toolbar popup: sign in, see current status. Chrome requires a real
// user gesture (this button click) to open chrome.identity.launchWebAuthFlow
// interactively -- sign-in can never happen silently, matching Icarus's own
// "never capture/act silently, opt-in always" principle.

const statusEl = document.getElementById("status");
const bridgeStatusEl = document.getElementById("bridge-status");
const btn = document.getElementById("signin");
const connectMacBtn = document.getElementById("connect-mac");

async function refresh() {
  chrome.runtime.sendMessage({ action: "bridgePing" }, (response) => {
    if (response && response.ok) {
      bridgeStatusEl.textContent = response.data && response.data.signed_in
        ? "Mac app connected and signed in."
        : "Mac app connected; sign in there to use its credential.";
      connectMacBtn.textContent = "Reconnect Mac app";
    } else {
      bridgeStatusEl.textContent = "Mac app bridge not connected.";
      connectMacBtn.textContent = "Connect Mac app";
    }
  });
  const { icarus_token } = await chrome.storage.local.get("icarus_token");
  if (icarus_token) {
    statusEl.textContent = "Signed in.";
    btn.textContent = "Sign in again";
  } else {
    statusEl.textContent = "Not signed in.";
    btn.textContent = "Sign in with GitHub";
  }
}

connectMacBtn.addEventListener("click", () => {
  const origin = `chrome-extension://${chrome.runtime.id}/`;
  window.location.href = `icarus://install-extension-bridge?origin=${encodeURIComponent(origin)}`;
});

btn.addEventListener("click", () => {
  btn.disabled = true;
  statusEl.textContent = "Signing in...";
  chrome.runtime.sendMessage({ action: "signIn" }, (response) => {
    btn.disabled = false;
    if (response && response.ok) {
      refresh();
    } else {
      statusEl.textContent = "Sign-in failed: " + ((response && response.error) || "unknown error");
    }
  });
});

refresh();
