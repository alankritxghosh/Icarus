// extension/popup.js
// Minimal toolbar popup: sign in, see current status. Chrome requires a real
// user gesture (this button click) to open chrome.identity.launchWebAuthFlow
// interactively -- sign-in can never happen silently, matching Icarus's own
// "never capture/act silently, opt-in always" principle.

const statusEl = document.getElementById("status");
const btn = document.getElementById("signin");

async function refresh() {
  const { icarus_token } = await chrome.storage.local.get("icarus_token");
  if (icarus_token) {
    statusEl.textContent = "Signed in.";
    btn.textContent = "Sign in again";
  } else {
    statusEl.textContent = "Not signed in.";
    btn.textContent = "Sign in with GitHub";
  }
}

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
