// The one Icarus brain this site talks to -- shared so next.config.ts's
// /api/ask rewrite and the server-side auth route handlers can never drift
// onto two different URLs. next.config.ts already imports from `src/`
// (`src/generated/release.json`), so importing this file there too is the
// established pattern, not a new one.
export const BRAIN_URL =
  "https://icarus-brain.whitecliff-26814629.centralindia.azurecontainerapps.io";
