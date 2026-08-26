import type { NextConfig } from "next";

const BRAIN =
  "https://icarus-brain.whitecliff-26814629.centralindia.azurecontainerapps.io";

const nextConfig: NextConfig = {
  async rewrites() {
    // Same contract the static site had in vercel.json: the browser calls a
    // same-origin path and Vercel proxies it, so there is no CORS dance and no
    // brain URL in client code.
    return [{ source: "/api/ask", destination: `${BRAIN}/ask` }];
  },
  async redirects() {
    // Every /Icarus.dmg link already in the wild -- cold emails, the old site,
    // an appcast an installed copy cached weeks ago -- has to keep resolving.
    // The binary now lives in GitHub Releases, so these forward rather than
    // 404. Permanent redirects, because the destination is versioned and
    // stable; the site simply stops being a file host.
    return [
      { source: "/Icarus.dmg", destination: "https://github.com/alankritxghosh/Icarus-Website/releases/download/v0.1.7/Icarus.dmg", permanent: true },
      { source: "/icarus-extension.zip", destination: "https://github.com/alankritxghosh/Icarus-Website/releases/download/v0.1.7/icarus-extension.zip", permanent: true },
    ];
  },
  async headers() {
    // install.sh must render in the browser, not download. The site tells
    // people to `less install.sh` and read it before running it, and that
    // instruction is worthless if the file arrives as an attachment.
    return [
      {
        source: "/install.sh",
        headers: [{ key: "Content-Type", value: "text/plain; charset=utf-8" }],
      },
    ];
  },
};

export default nextConfig;
