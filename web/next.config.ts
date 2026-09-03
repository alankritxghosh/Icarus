import type { NextConfig } from "next";
import release from "./src/generated/release.json";
import { BRAIN_URL as BRAIN } from "./src/lib/brain";

// Next emits small inline bootstrap scripts and Tailwind emits inline styles;
// those two allowances are explicit. Everything else stays same-origin, and
// the page cannot become an object/embed target or submit forms elsewhere.
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "media-src 'self'",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "upgrade-insecure-requests",
].join("; ");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    // Same contract the static site had in vercel.json: the browser calls a
    // same-origin path and Vercel proxies it, so there is no CORS dance and no
    // brain URL in client code.
    return [
      { source: "/api/ask", destination: `${BRAIN}/ask` },
      // GitHub's OAuth redirect for "web" mode lands here. This must be a
      // transparent proxy (not a route handler): the brain's callback
      // handler replies with a bare relative `Location: /?session=...`
      // (demo/github_oauth.py's `_github_callback`), which only resolves to
      // THIS site's root because the browser never sees the brain's own
      // origin -- Vercel forwards the response as if it came from here. A
      // route handler re-issuing its own redirect would work too, but this
      // is one line and matches the /api/ask precedent exactly.
      { source: "/auth/github/callback", destination: `${BRAIN}/auth/github/callback` },
    ];
  },
  async redirects() {
    // Every /Icarus.dmg link already in the wild -- cold emails, the old site,
    // an appcast an installed copy cached weeks ago -- has to keep resolving.
    // The binary now lives in GitHub Releases, so these forward rather than
    // 404. Permanent redirects, because the destination is versioned and
    // stable; the site simply stops being a file host.
    return [
      { source: "/Icarus.dmg", destination: release.url, permanent: true },
      {
        source: "/icarus-extension.zip",
        destination: `${release.assets_base}/${release.extension.name}`,
        permanent: true,
      },
    ];
  },
  async headers() {
    // install.sh must render in the browser, not download. The site tells
    // people to `less install.sh` and read it before running it, and that
    // instruction is worthless if the file arrives as an attachment.
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: CONTENT_SECURITY_POLICY },
        ],
      },
      {
        source: "/install.sh",
        headers: [{ key: "Content-Type", value: "text/plain; charset=utf-8" }],
      },
    ];
  },
};

export default nextConfig;
