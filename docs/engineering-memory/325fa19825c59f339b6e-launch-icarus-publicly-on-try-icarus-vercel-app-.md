<!-- icarus-agent-mode-decision:v1 id=325fa19825c59f339b6e7dd78d21701e467b0f745101fa329fc655ef4fd77f69 -->

# Launch Icarus publicly on try-icarus.vercel.app (a second Vercel project domain that auto-follows production), and keep icarus-website-kappa.vercel.app alive indefinitely because the shipped Mac app 0.1.10 has that URL compiled in as its Sparkle update feed.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Launch Icarus publicly on try-icarus.vercel.app (a second Vercel project domain that auto-follows production), and keep icarus-website-kappa.vercel.app alive indefinitely because the shipped Mac app 0.1.10 has that URL compiled in as its Sparkle update feed.

## Confirmed rationale

No custom domain is affordable now. The old production URL carries a random "-kappa" suffix that reads as unfinished for a launch. Renaming the Vercel project would free that subdomain and break auto-updates for every already-installed 0.1.10 copy, since the appcast URL is baked into the binary. Adding a second project domain is non-destructive: both URLs serve the same site, -kappa keeps the update feed working, and try-icarus.vercel.app becomes the public face (it also matches the site's #try anchor and the "try it on your repo" CTA). icarus-website / icarus-app / icarus-brain were all already taken.

## Alternatives considered

- Rename the Vercel project to drop -kappa
- Launch on the -kappa URL as-is
- Buy a cheap real domain (.xyz ~$1-12/yr)

## Affected paths

No affected paths were recorded.

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
